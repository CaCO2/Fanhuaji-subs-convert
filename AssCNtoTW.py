import os
import re
import zipfile
import shutil
import requests
import logging
from functools import lru_cache
from requests.adapters import HTTPAdapter, Retry    
    
# 設定欲翻譯的資料
FOLDER_PATH = (r'/home/pi/Downloads/For_translation')

session = requests.Session()
header = {"Content-type": "application/json", "Accept": "application/json"}
retries = Retry(
    total=3,  # Retry up to 3 times
    backoff_factor=5,  # Wait between retries
    status_forcelist=[500, 502, 503, 504],  # Retry on these HTTP errors
)
session.mount("https://", HTTPAdapter(max_retries=retries))

# 設置 translate_logger 和 process_logger
translate_logger = logging.getLogger('translate')
translate_logger.setLevel(logging.INFO)
process_logger = logging.getLogger('process')
process_logger.setLevel(logging.INFO)

print(os.path.abspath(FOLDER_PATH))
      
# 創建 file handlers
translate_handler = logging.FileHandler(FOLDER_PATH+r'/translate.log', mode='w', encoding='utf-8')
process_handler = logging.FileHandler(FOLDER_PATH+r'/process.log', mode='w', encoding='utf-8')

# 設置日誌格式
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
translate_handler.setFormatter(formatter)
process_handler.setFormatter(formatter)

console = logging.StreamHandler()

# 添加 handler 到 logger
translate_logger.addHandler(translate_handler)
translate_logger.addHandler(console)
process_logger.addHandler(process_handler)
process_logger.addHandler(console)

@lru_cache(maxsize=512) # 設置緩存大小(無限制)
def translate_text(text):
    """
    利用 zhconvert 的 API 翻譯中文文本
    """
    url = "https://api.zhconvert.org/convert"
    params = {"converter": "Taiwan", "text": text}
    try:
        response = session.get(url, headers=header, params=params, timeout=5)  # Set timeout
        response.raise_for_status()  # Raise error for bad responses (4xx, 5xx)
        return response.json()["data"]["text"]
    except requests.exceptions.ConnectionError:
        print("Connection error occurred. Retrying...")
        return translate_text(text)  # Retry the request
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}. Retrying...")
        return ""  # Return empty string if all retries fail

def translate_file(file_path):
    # 讀取檔案內容
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 找到所有需要翻譯的內容
    pattern = r',,(.*)'  # 匹配,,號後的所有文字
    match_iter = re.finditer(pattern, content)
    
    # 翻譯每個匹配到的內容
    for match in match_iter:
        text = match.group(1)
        translated_text = translate_text(text)
        if text != translated_text:                  
            translate_logger.info(f'translate before: {text}')
            translate_logger.info(f'translate after: {translated_text}')
            if translated_text !='':
                content = content.replace(match.group(), ',,' + translated_text)
    # 將翻譯後的內容寫回到原檔案
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)

def translate_folder(folder_path):
#    with open(os.path.join(FOLDER_PATH, 'translate.log'), 'a', encoding='utf-8') as f:
        # 翻譯資料夾中的所有檔案
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                file_path = os.path.join(root, file)
                ext = os.path.splitext(file_path)[1].lower()

                if ext == '.ass':
                    # 翻譯ass檔案
#                    print('Translating file: {}'.format(file_path))
                    process_logger.info('Translating file: {}'.format(file_path))
                    translate_file(file_path)
                    # 記錄翻譯完成的檔案路徑
                    process_logger.info('Translated: {}'.format(file_path))
#                    print('Translated: {}'.format(file_path))

        # 遍歷資料夾內所有檔案和子資料夾，檢查是否有壓縮檔案
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                file_path = os.path.join(root, file)
                ext = os.path.splitext(file_path)[1].lower()

                if ext == '.zip':
                    # 檢查壓縮檔案內部是否有文本檔案
                    has_txt_file = False
                    with zipfile.ZipFile(file_path, 'r') as zip_ref:
                        for name in zip_ref.namelist():
                            if os.path.splitext(name)[1].lower() == '.txt':
                                has_txt_file = True
                                break

                    if has_txt_file:
                        # 解壓縮壓縮檔案
                        process_logger.info('Extracting {}...'.format(file_path))
#                        print('Extracting {}...'.format(file_path))
                        with zipfile.ZipFile(file_path, 'r') as zip_ref:
                            zip_ref.extractall(os.path.join(root, os.path.splitext(file)[0]))

                        # 遞迴翻譯解壓縮後的資料夾
                        folder_path_new = os.path.join(root, os.path.splitext(file)[0])
#                        print('Translating folder: {}'.format(folder_path_new))
                        process_logger.info('Translating folder: {}'.format(folder_path_new))
                        translate_folder(folder_path_new)

                        # 壓縮資料夾並刪除原始資料夾
#                        print('Recompressing {}...'.format(folder_path_new))
                        process_logger.info('Recompressing {}...'.format(folder_path_new))
                        with zipfile.ZipFile(os.path.join(root, file), 'w') as zip_ref:
                            for root_new, dirs_new, files_new in os.walk(folder_path_new):
                                for file_new in files_new:
                                    file_path_new = os.path.join(root_new, file_new)
                                    zip_ref.write(file_path_new, os.path.relpath(file_path_new, folder_path_new))

                        shutil.rmtree(folder_path_new)
                        # 記錄壓縮完成的檔案路徑
#                        print('Recompressed: {}'.format(os.path.join(root, file)))
                        process_logger.info('Recompressed: {}'.format(os.path.join(root, file)))
                    else:
#                        print('Skipping empty zip file: {}'.format(file_path))
                        process_logger.info('Skipping empty zip file: {}'.format(file_path))


if __name__ == "__main__":
    translate_folder(FOLDER_PATH)
