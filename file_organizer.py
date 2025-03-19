import sys
import os
import shutil
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QFileDialog, QLabel, 
                             QListWidget, QMessageBox, QProgressBar, QCheckBox)
from PyQt5.QtCore import Qt, QThread, pyqtSignal


class FileOrganizerThread(QThread):
    """Thread for organizing files without freezing the GUI"""
    progress_update = pyqtSignal(int)
    finished_signal = pyqtSignal(dict)
    error_signal = pyqtSignal(str)
    preview_signal = pyqtSignal(dict)

    def __init__(self, source_dir, preview_only=False):
        super().__init__()
        self.source_dir = source_dir
        self.preview_only = preview_only

    def run(self):
        try:
            # Dictionary to store extension counts
            organized_files = {}
            
            # Get all files in the directory
            files = [f for f in os.listdir(self.source_dir) 
                    if os.path.isfile(os.path.join(self.source_dir, f))]
            
            if not files:
                self.error_signal.emit("No files found in the selected directory.")
                return
            
            # Calculate total files for progress bar
            total_files = len(files)
            
            # Process each file
            for index, file in enumerate(files):
                # Skip hidden files
                if file.startswith('.'):
                    continue
                
                # Get file extension
                _, ext = os.path.splitext(file)
                ext = ext.lower()[1:]  # Remove the dot and convert to lowercase
                
                if not ext:
                    ext = 'no_extension'
                
                # Update counter
                organized_files[ext] = organized_files.get(ext, 0) + 1
                
                # Only move files if not in preview mode
                if not self.preview_only:
                    # Create directory for the extension if it doesn't exist
                    ext_dir = os.path.join(self.source_dir, ext)
                    if not os.path.exists(ext_dir):
                        os.makedirs(ext_dir)
                    
                    # Move file to the appropriate directory
                    source_path = os.path.join(self.source_dir, file)
                    dest_path = os.path.join(ext_dir, file)
                    
                    # Handle file name conflicts
                    if os.path.exists(dest_path):
                        base, extension = os.path.splitext(file)
                        counter = 1
                        while os.path.exists(os.path.join(ext_dir, f"{base}_{counter}{extension}")):
                            counter += 1
                        dest_path = os.path.join(ext_dir, f"{base}_{counter}{extension}")
                    
                    shutil.move(source_path, dest_path)
                
                # Update progress
                progress = int((index + 1) / total_files * 100)
                self.progress_update.emit(progress)
            
            # Emit appropriate signal based on mode
            if self.preview_only:
                self.preview_signal.emit(organized_files)
            else:
                self.finished_signal.emit(organized_files)
            
        except Exception as e:
            self.error_signal.emit(f"Error {'previewing' if self.preview_only else 'organizing'} files: {str(e)}")


class FileOrganizerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("File Organizer")
        self.setMinimumSize(600, 400)
        self.initUI()
        
    def initUI(self):
        # Main widget and layout
        main_widget = QWidget()
        main_layout = QVBoxLayout()
        
        # Directory selection section
        dir_layout = QHBoxLayout()
        self.dir_label = QLabel("No directory selected")
        self.dir_label.setWordWrap(True)
        
        self.select_button = QPushButton("Select Directory")
        self.select_button.clicked.connect(self.select_directory)
        
        dir_layout.addWidget(self.dir_label, 1)
        dir_layout.addWidget(self.select_button, 0)
        
        # Buttons layout
        button_layout = QHBoxLayout()
        
        # Preview checkbox
        self.preview_checkbox = QCheckBox("Preview Mode")
        self.preview_checkbox.setToolTip("Show what would be organized without moving files")
        
        # Preview button
        self.preview_button = QPushButton("Preview")
        self.preview_button.clicked.connect(self.preview_files)
        self.preview_button.setEnabled(False)
        
        # Organize button
        self.organize_button = QPushButton("Organize Files")
        self.organize_button.clicked.connect(self.organize_files)
        self.organize_button.setEnabled(False)
        
        button_layout.addWidget(self.preview_checkbox)
        button_layout.addWidget(self.preview_button)
        button_layout.addWidget(self.organize_button)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        
        # Results list
        self.results_list = QListWidget()
        
        # Status label
        self.status_label = QLabel("Ready")
        self.status_label.setAlignment(Qt.AlignCenter)
        
        # Add widgets to main layout
        main_layout.addLayout(dir_layout)
        main_layout.addLayout(button_layout)
        main_layout.addWidget(self.progress_bar)
        main_layout.addWidget(self.results_list)
        main_layout.addWidget(self.status_label)
        
        # Set main layout
        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)
        
        # Initialize variables
        self.selected_dir = None
        self.organizer_thread = None
    
    def select_directory(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Select Directory to Organize")
        if dir_path:
            self.selected_dir = dir_path
            self.dir_label.setText(f"Selected: {dir_path}")
            self.preview_button.setEnabled(True)
            self.organize_button.setEnabled(True)
            self.results_list.clear()
            self.status_label.setText("Ready to organize files")
    
    def preview_files(self):
        """Preview what files would be organized without actually moving them"""
        if not self.selected_dir:
            QMessageBox.warning(self, "Warning", "Please select a directory first.")
            return
        
        # Disable buttons and show progress bar
        self.toggle_ui_elements(False)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.results_list.clear()
        self.status_label.setText("Previewing organization...")
        
        # Create and start the organizer thread in preview mode
        self.organizer_thread = FileOrganizerThread(self.selected_dir, preview_only=True)
        self.organizer_thread.progress_update.connect(self.update_progress)
        self.organizer_thread.preview_signal.connect(self.preview_finished)
        self.organizer_thread.error_signal.connect(self.show_error)
        self.organizer_thread.start()
    
    def organize_files(self):
        if not self.selected_dir:
            QMessageBox.warning(self, "Warning", "Please select a directory first.")
            return
        
        # Confirm before organizing
        confirm = QMessageBox.question(
            self, 
            "Confirm Organization",
            "This will organize all files in the selected directory by moving them into subfolders based on their extension. Continue?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if confirm == QMessageBox.Yes:
            # Disable buttons and show progress bar
            self.toggle_ui_elements(False)
            self.progress_bar.setValue(0)
            self.progress_bar.setVisible(True)
            self.results_list.clear()
            self.status_label.setText("Organizing files...")
            
            # Create and start the organizer thread
            self.organizer_thread = FileOrganizerThread(self.selected_dir, preview_only=False)
            self.organizer_thread.progress_update.connect(self.update_progress)
            self.organizer_thread.finished_signal.connect(self.organization_finished)
            self.organizer_thread.error_signal.connect(self.show_error)
            self.organizer_thread.start()
    
    def update_progress(self, value):
        self.progress_bar.setValue(value)
    
    def preview_finished(self, organized_files):
        # Re-enable buttons
        self.toggle_ui_elements(True)
        
        # Update results list
        self.results_list.clear()
        total_files = sum(organized_files.values())
        self.results_list.addItem(f"PREVIEW: Total files that would be organized: {total_files}")
        
        for ext, count in sorted(organized_files.items()):
            folder_name = ext if ext else "no_extension"
            self.results_list.addItem(f"{folder_name}: {count} files would be moved")
        
        # Update status
        self.status_label.setText("Preview completed! Use Organize Files to perform the actual organization.")
    
    def organization_finished(self, organized_files):
        # Re-enable buttons
        self.toggle_ui_elements(True)
        
        # Update results list
        self.results_list.clear()
        total_files = sum(organized_files.values())
        self.results_list.addItem(f"Total files organized: {total_files}")
        
        for ext, count in sorted(organized_files.items()):
            folder_name = ext if ext else "no_extension"
            self.results_list.addItem(f"{folder_name}: {count} files")
        
        # Update status
        self.status_label.setText("Organization completed!")
    
    def show_error(self, error_message):
        # Re-enable buttons
        self.toggle_ui_elements(True)
        
        # Show error message
        QMessageBox.critical(self, "Error", error_message)
        self.status_label.setText("Error occurred")
    
    def toggle_ui_elements(self, enabled):
        """Enable or disable UI elements during operations"""
        self.organize_button.setEnabled(enabled)
        self.preview_button.setEnabled(enabled)
        self.select_button.setEnabled(enabled)
        self.preview_checkbox.setEnabled(enabled)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = FileOrganizerApp()
    window.show()
    sys.exit(app.exec_())