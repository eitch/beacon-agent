import  logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s.%(msecs)03d %(module)s %(levelname)s:\t%(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S'
                    )

from smartctl_reader import SmartCtlReader

smartctl = SmartCtlReader()
smartctl.read_smartdata_for_all_devices()
smartctl.print_all_details()