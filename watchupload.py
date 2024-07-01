import os
import time
import subprocess
import requests
from google.cloud import storage
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import pyperclip


class FileChangedHandler(FileSystemEventHandler):
    def __init__(self, folder_path, extensions):
        super().__init__()
        self.folder_path = folder_path
        self.extensions = extensions

    def on_created(self, event):
        if (not event.is_directory and os.path.isfile(event.src_path)
                and (self.extensions is False or any(event.src_path.endswith(ext)) for ext in self.extensions)):
            run_process(event.src_path)


def watch_folder(folder_path, extensions):
    event_handler = FileChangedHandler(folder_path, extensions)
    observer = Observer()
    observer.schedule(event_handler, folder_path, recursive=True)
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    except Exception as e:
        print(e)
    observer.join()


def run_process(file_path):
    public_url = upload_to_google_cloud(file_path)
    if public_url is not False:
        print(public_url)
        shortened_url = shorten_url(custom_url(public_url))
        print(shortened_url)
        if len(shortened_url) > 0:
            # Copy the URL to the clipboard
            if copy_to_clipboard(shortened_url):
                print("Copied to clipboard: " + shortened_url)
            else:
                print("Failed to copy to clipboard: " + shortened_url)

            # Log the shortened URL to a CSV file
            file_name = os.path.basename(file_path)
            log_to_file(shortened_url + "," + file_name)


def upload_to_google_cloud(file_path):
    global bucket_name
    global bucket_folder

    try:
        file_name = os.path.basename(file_path)

        storage_client = storage.Client()

        bucket = storage_client.bucket(bucket_name)

        # Create the folder if it doesn't exist
        blob = bucket.blob(bucket_folder + '/')
        if not blob.exists():
            blob.upload_from_string('')

        # Create the file if it doesn't exist
        blob = bucket.blob(bucket_folder + "/" + file_name)
        if not blob.exists():
            blob.upload_from_filename(file_path)

        blob.make_public()

        public_url = custom_url(blob.public_url)

        if len(public_url) > 0:
            return public_url

        return False

    except Exception as e:
        print(e)
        return False


def custom_url(url):
    # remove the string storage.googleapis.com/
    return url.replace("storage.googleapis.com/", "")


def shorten_url(url):
    try:
        response = requests.post("https://is.gd/create.php", data={"format": "json", "url": url})
        return response.json()["shorturl"]
    except Exception as e:
        print(e)
        return False


def copy_to_clipboard(text):
    try:
        pyperclip.copy(text)
        subprocess.Popen(['notify-send', 'Copied to clipboard: ' + text])
        return True
    except pyperclip.PyperclipException:
        return False


def log_to_file(text):
    with open("log.csv", "a") as f:
        f.write(text + "\n")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("folder_path", help="Path to the folder to watch")
    parser.add_argument("bucket_name", help="Bucket name to upload files to")
    parser.add_argument("bucket_folder", help="Folder in bucket to upload files to")
    parser.add_argument("credentials", help="Path to the credentials JSON file downloaded from Google Cloud Platform")
    parser.add_argument("--extensions", help="Comma-separated list of file extensions to listen for")
    args = parser.parse_args()

    bucket_name = args.bucket_name
    bucket_folder = args.bucket_folder
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = args.credentials

    if args.extensions:
        extensions = args.extensions[0].split(",")
    else:
        extensions = False
    watch_folder(args.folder_path, extensions)
