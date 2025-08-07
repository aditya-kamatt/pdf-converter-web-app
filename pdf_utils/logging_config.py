"""
Logging configuration utilities (placeholder).
"""

import logging
import logging.config

def setup_logging():
    """
    Set up logging for the application.
    This configuration sends logs to the console.
    """
    LOGGING_CONFIG = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'default': {
                'format': '%(asctime)s - %(levelname)s - %(name)s - %(message)s',
                'datefmt': '%Y-%m-%d %H:%M:%S',
            },
        },
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
                'level': 'DEBUG',
                'formatter': 'default',
                'stream': 'ext://sys.stdout',  # Or sys.stderr
            },
        },
        'loggers': {
            '': {  # root logger
                'level': 'DEBUG',
                'handlers': ['console'],
                'propagate': True,
            },
            'pdfminer': { # pdfminer logs are very verbose, so we set it to a higher level
                'level': 'INFO',
                'handlers': ['console'],
                'propagate': False,
            }
        }
    }
    logging.config.dictConfig(LOGGING_CONFIG) 