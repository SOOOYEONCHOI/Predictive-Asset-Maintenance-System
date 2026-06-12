import os
import json
import logging
import logging.config
from datetime import datetime

LOG_PATH = os.getenv("LOG_PATH", "/app/logs")

class LoggingLogger(object):
    def __new__(cls, *args, **kwargs):
        if not hasattr(cls, "_instance"):
            cls._instance = super(LoggingLogger, cls).__new__(cls)
            print("LoggingLogger __new__")
        else:
            print("LoggingLogger recycle")
        return cls._instance

    def __init__(self, data=None):
        cls = type(self)
        if not hasattr(cls, "_init"):
            self.data = data
            print("LoggingLogger __init__ Start")

            try:
                with open(os.path.join(os.path.dirname(__file__), 'logger.json').replace("\\","/")) as f:
                    logging_config = json.load(f)

                    date = datetime.now().strftime("%Y%m%d")
                    path_dir = LOG_PATH

                    os.makedirs(path_dir, exist_ok=True)
                    print(f"로그 디렉토리 생성/확인: {path_dir}")

                    debug_file = os.path.join(path_dir, f"{date}_LOG_DEBUG.log").replace("\\","/")
                    info_file = os.path.join(path_dir, f"{date}_LOG_INFO.log").replace("\\","/")
                    error_file = os.path.join(path_dir, f"{date}_LOG_ERROR.log").replace("\\","/")

                    logging_config['handlers']['file_debug']['filename'] = debug_file
                    logging_config['handlers']['file_info']['filename'] = info_file
                    logging_config['handlers']['file_error']['filename'] = error_file

                    print(f"로그 파일 경로 설정:")
                    print(f"  DEBUG: {debug_file}")
                    print(f"  INFO: {info_file}")
                    print(f"  ERROR: {error_file}")

                    logging.config.dictConfig(logging_config)

                    logger = logging.getLogger()
                    logger.info("로그 시스템 초기화 완료")
                    logger.debug("DEBUG 로그 테스트")
                    logger.error("ERROR 로그 테스트")

            except Exception as e:
                print(f"로그 설정 중 오류 발생: {e}")
                logging.basicConfig(
                    level=logging.DEBUG,
                    format='[%(asctime)s][%(levelname)s][%(filename)s:%(lineno)d] %(message)s',
                    handlers=[
                        logging.StreamHandler(),
                        logging.FileHandler(os.path.join(path_dir, f"{date}_LOG_FALLBACK.log"))
                    ]
                )

            print("LoggingLogger __init__ Done")
            cls._init = True

    def getLogger(self):
        return logging.getLogger()