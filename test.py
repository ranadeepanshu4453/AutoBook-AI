import sys

_exit = sys.exit

def my_exit(c=0):
    import traceback
    traceback.print_stack()
    print('EXIT CALLED WITH:', c)
    _exit(c)

sys.exit = my_exit

import uvicorn
uvicorn.run('app.main:app', host='0.0.0.0', port=8000, log_level='debug')