try:
    from env import *
except ImportError:
    print('env.py not found, creating a new one.')
    import os

    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    with open('env.py', 'w') as fout:
        with open('env_example.py') as fin:
            fout.write(fin.read())

    from env import *
