#!/usr/bin/python

# create a bunch of job scripts
from config import config
from subprocess import call
import glob
import os
import socket
import getpass
import datetime as dt
import supereeg as se
from supereeg.helpers import filter_subj

# ====== MODIFY ONLY THE CODE BETWEEN THESE LINES ======
try:
    os.stat(config['resultsdir'])
except:
    os.makedirs(config['resultsdir'])


def electrode_search(fname):
    values = filter_subj(fname, return_locs=True)
    if values is None:
        return 0
    else:
        meta, locs = values
        return locs.shape[0]


# each job command should be formatted as a string
job_script = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'recon.py')

bos = ('BW001.bo', 'TJ013.bo')
files = list(map(lambda x: os.path.join(config['datadir'],x), bos))
#print(files)
#files = glob.glob(os.path.join(config['datadir'],'*.bo'))

file_nums = [(a, i) for item, (a,b) in enumerate(zip(files, map(lambda e :electrode_search(e), files))) for i in range(b)]

file_nums =file_nums[0:12]
# options for model: 'pyFR_union', 'example_model', 'gray'
model = str('pyFR_union')

radius = str('20')

job_commands = list(map(lambda x: x[0]+" "+str(x[1][0])+" "+str(x[1][1])+" " + model + " " + radius, zip([job_script]* len(file_nums), file_nums)))

# job_names should specify the file name of each script (as a list, of the same length as job_commands)
job_names = list(map(lambda x: os.path.splitext(os.path.basename(x[0]))[0]+"_"+str(x[1])+"_" + model+ "_" + radius + '.sh', file_nums))



# ====== MODIFY ONLY THE CODE BETWEEN THESE LINES ======

assert(len(job_commands) == len(job_names))


# job_command is referenced in the run_job.sh script
# noinspection PyBroadException,PyUnusedLocal
def create_job(name, job_command):
    # noinspection PyUnusedLocal,PyShadowingNames
    def create_helper(s, job_command):
        x = [i for i, char in enumerate(s) if char == '<']
        y = [i for i, char in enumerate(s) if char == '>']
        if len(x) == 0:
            return s

        q = ''
        index = 0
        for i in range(len(x)):
            q += s[index:x[i]]
            unpacked = eval(s[x[i]+1:y[i]])
            q += str(unpacked)
            index = y[i]+1
        return q

    # create script directory if it doesn't already exist
    try:
        os.stat(config['scriptdir'])
    except:
        os.makedirs(config['scriptdir'])

    template_fd = open(config['template'], 'r')
    job_fname = os.path.join(config['scriptdir'], name)
    new_fd = open(job_fname, 'w+')

    while True:
        next_line = template_fd.readline()
        if len(next_line) == 0:
            break
        new_fd.writelines(create_helper(next_line, job_command))
    template_fd.close()
    new_fd.close()
    return job_fname


# noinspection PyBroadException
def lock(lockfile):
    try:
        os.stat(lockfile)
        return False
    except:
        fd = open(lockfile, 'w')
        fd.writelines('LOCK CREATE TIME: ' + str(dt.datetime.now()) + '\n')
        fd.writelines('HOST: ' + socket.gethostname() + '\n')
        fd.writelines('USER: ' + getpass.getuser() + '\n')
        fd.writelines('\n-----\nCONFIG\n-----\n')
        for k in config.keys():
            fd.writelines(k.upper() + ': ' + str(config[k]) + '\n')
        fd.close()
        return True


# noinspection PyBroadException
def release(lockfile):
    try:
        os.stat(lockfile)
        os.remove(lockfile)
        return True
    except:
        return False


script_dir = config['scriptdir']
lock_dir = config['lockdir']
lock_dir_exists = False
# noinspection PyBroadException
try:
    os.stat(lock_dir)
    lock_dir_exists = True
except:
    os.makedirs(lock_dir)

# noinspection PyBroadException
try:
    os.stat(config['startdir'])
except:
    os.makedirs(config['startdir'])

locks = list()
for n, c in zip(job_names, job_commands):
    # if the submission script crashes before all jobs are submitted, the lockfile system ensures that only
    # not-yet-submitted jobs will be submitted the next time this script runs
    next_lockfile = os.path.join(lock_dir, n+'.LOCK')
    locks.append(next_lockfile)
    if not os.path.isfile(os.path.join(script_dir, n)):
        if lock(next_lockfile):
            next_job = create_job(n, c)

            if (socket.gethostname() == 'discovery.hpcc.dartmouth.edu') or (socket.gethostname() == 'ndoli.hpcc.dartmouth.edu'):
                submit_command = 'echo "[SUBMITTING JOB: ' + next_job + ']"; qsub'
            else:
                submit_command = 'echo "[RUNNING JOB: ' + next_job + ']"; sh'

            call(submit_command + " " + next_job, shell=True)

# all jobs have been submitted; release all locks
for l in locks:
    release(l)
if not lock_dir_exists:  # remove lock directory if it was created here
    os.rmdir(lock_dir)
