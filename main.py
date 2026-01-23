import os
import json
import logging
from urllib.parse import urlparse
from typing import Dict, List

import requests
from tqdm import tqdm
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class DogImageDownloader:
    """A class for uploading dog images and saving them to YandexDisk"""

    DOG_API_BASE = "https://dog.ceo/api"
    YADISK_API_BASE = "https://cloud-api.yandex.net/v1/disk"

    def __init__(self, yadisk_token: str, breed: str):
        """Initializing the loader"""
        self.yadisk_token = yadisk_token
        self.breed = breed
        self.headers = {"Authorization": f"OAuth {yadisk_token}"}
        self.results: List[Dict[str, str]] = []

    def _get_sub_breeds(self) -> List[str]:
        """Gets a list of sub-breeds for the specified breed"""
        url = f"{self.DOG_API_BASE}/breed/{self.breed}/list"
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        return data.get("message", [])

    def _get_random_image_url(self, breed_path: str) -> str:
        """Gets the URL of a random image for a given breed or sub-breed"""
        url = f"{self.DOG_API_BASE}/breed/{breed_path}/images/random"
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        return data["message"]

    def _extract_filename_from_url(self, url: str) -> str:
        """Extracts the file name from the URL"""
        parsed = urlparse(url)
        return os.path.basename(parsed.path)

    def _create_folder_on_yadisk(self, folder_name: str) -> None:
        """Creates a folder on YandexDisk"""
        url = f"{self.YADISK_API_BASE}/resources"
        params = {"path": folder_name}
        response = requests.put(url, headers=self.headers, params=params)
        if response.status_code not in (201, 409):
            response.raise_for_status()

    def _upload_file_by_url(self, file_url: str, remote_path: str) -> None:
        """Uploads a file to Yandex.Disk by URL without saving it locally"""
        url = f"{self.YADISK_API_BASE}/resources/upload"
        params = {
            "url": file_url,
            "path": remote_path,
            "overwrite": "true"
        }
        response = requests.post(url, headers=self.headers, params=params)
        response.raise_for_status()

        operation_href = response.json().get("href")
        if operation_href:
            while True:
                op_response = requests.get(operation_href, headers=self.headers)
                op_data = op_response.json()
                if op_data.get("status") == "success":
                    break
                elif op_data.get("status") == "failed":
                    raise RuntimeError(f"Yandex.Disk upload failed: {op_data}")

    def run(self) -> None:
        """The main method for starting the download process"""
        logger.info(f"Начинаем обработку породы: {self.breed}")

        sub_breeds = self._get_sub_breeds()
        if not sub_breeds:
            logger.info("Подпород не найдено. Загружаем изображение основной породы.")
            breeds_to_process = [self.breed]
        else:
            logger.info(f"Найдено подпород: {len(sub_breeds)}")
            breeds_to_process = [f"{self.breed}/{sub}" for sub in sub_breeds]

        folder_name = self.breed
        self._create_folder_on_yadisk(folder_name)

        for breed_path in tqdm(breeds_to_process, desc="Загрузка изображений"):
            try:
                image_url = self._get_random_image_url(breed_path)
                filename = self._extract_filename_from_url(image_url)
                safe_breed_name = breed_path.replace("/", "-")
                remote_filename = f"{safe_breed_name}_{filename}"
                remote_path = f"{folder_name}/{remote_filename}"

                self._upload_file_by_url(image_url, remote_path)

                self.results.append({
                    "breed_path": breed_path,
                    "image_url": image_url,
                    "remote_path": remote_path
                })

                logger.info(f"Загружено: {remote_path}")
            except Exception as e:
                logger.error(f"Ошибка при обработке {breed_path}: {e}")

        # To -> JSON
        results_file = f"{self.breed}_results.json"
        with open(results_file, "w", encoding="utf-8") as file:
            json.dump(self.results, file, indent=4, ensure_ascii=False)

        logger.info(f"Результаты сохранены в {results_file}")
        logger.info("Завершено успешно.")


def main():
    """Main"""
    yadisk_token = os.getenv("YADISK_OAUTH_TOKEN")
    if not yadisk_token:
        raise EnvironmentError(
            "Переменная окружения YADISK_OAUTH_TOKEN не установлена. "
            "Создайте файл .env с содержимым: YADISK_OAUTH_TOKEN=ваш_токен"
        )

    breed = input("Введите название породы (например, spaniel): ").strip().lower()
    if not breed:
        raise ValueError("Порода не может быть пустой.")

    downloader = DogImageDownloader(yadisk_token=yadisk_token, breed=breed)
    downloader.run()


if __name__ == "__main__":
    main()



