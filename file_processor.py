class FileProcessor:

    def __init__(self, dir_path=None):
        self.dir_path = dir_path

    def save_file(self, file_path, file_content):
        with open(file_path, 'a') as file:
            file.write(file_content)

    def read_file(self, file_path):
        with open(file_path,'r') as file:
            return file.read().splitlines()