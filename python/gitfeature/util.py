import logging
import logging.handlers

def initlog(log_filename):
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    # create file handler which logs even debug messages
    #fh = logging.FileHandler(log_filename)
    fh = logging.handlers.RotatingFileHandler(
            log_filename,
            maxBytes=int(1e4),
            backupCount=2)
    fh.setLevel(logging.DEBUG)
    # create formatter and add it to the handlers
    formatter = logging.Formatter(
            '%(asctime)s -'\
                    ' %(levelname)s -'\
                    ' %(message)s')
    fh.setFormatter(formatter)
    # add the handlers to logger
    logger.addHandler(fh)

#Functions to display informations in log
verbose = logging.info
debug = logging.debug

