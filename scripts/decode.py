import json
import numpy as np
import struct
import sys

sys.path.append('build')
from metadata_pb2 import JobDescriptor, VideoDescriptor

def load_output_buffers(dataset_name, job_name, column, fn, intvl=None):
    job = JobDescriptor()

    with open('db/{}_job_descriptor.bin'.format(job_name), 'rb') as f:
        job.ParseFromString(f.read())

    for entry in job.videos:
        video = {'index': entry.index, 'buffers': []}

        metadata = VideoDescriptor()
        with open('db/{}_dataset/{}_metadata.bin'.format(dataset_name, entry.index), 'rb') as f:
            metadata.ParseFromString(f.read())

        (istart, iend) = intvl if intvl is not None else (0, sys.maxint)
        for ivl in entry.intervals:
            start = ivl.start
            end = ivl.end
            path = 'db/{}_job/{}_{}_{}-{}.bin'.format(job_name, entry.index, column, start, end)
            if start > iend or end < istart: continue
            try:
                with open(path, 'rb') as f:
                    lens = []
                    start_pos = sys.maxint
                    pos = 0
                    for i in range(end-start):
                        idx = i + start
                        byts = f.read(8)
                        (buf_len,) = struct.unpack("l", byts)
                        old_pos = pos
                        pos += buf_len
                        if (idx >= istart and idx <= iend):
                            if start_pos == sys.maxint:
                                start_pos = old_pos
                            lens.append(buf_len)

                    bufs = []
                    f.seek((end-start) * 8 + start_pos)
                    for buf_len in lens:
                        buf = f.read(buf_len)
                        item = fn(buf, metadata)
                        bufs.append(item)

                    video['buffers'] += bufs
            except IOError as e:
                print("{}".format(e))
        yield video

def get_output_size(job_name):
    with open('db/{}_job_descriptor.bin'.format(job_name), 'r') as f:
        job = json.loads(f.read())

    return job['videos'][0]['intervals'][-1][1]

def scanner_loader(column):
    def decorator(f):
        def loader(dataset_name, job_name):
            return load_output_buffers(dataset_name, job_name, column, f)
        return loader
    return decorator

@scanner_loader('histogram')
def load_histograms(buf, metadata):
    return np.split(np.frombuffer(buf, dtype=np.dtype(np.float32)), 3)

@scanner_loader('faces')
def load_faces(buf, metadata):
    num_faces = len(buf) / 16
    faces = []
    for i in range(num_faces):
        faces.append(struct.unpack("iiii", buf[(16*i):(16*(i+1))]))
    return faces

@scanner_loader('opticalflow')
def load_opticalflow(buf, metadata):
    return np.frombuffer(buf, dtype=np.dtype(np.float32)).reshape((metadata.width, metadata.height, 2))

@scanner_loader('cameramotion')
def load_cameramotion(buf, metadata):
    return struct.unpack('d', buf)

@scanner_loader('fc25')
def load_features(buf, metadata):
    return np.frombuffer(buf, dtype=np.dtype(np.float32))

cv_version = 3 # int(cv2.__version__.split('.')[0])

def save_movie_info():
    np.save('{}_faces.npy'.format(JOB), load_faces(JOB)[0]['buffers'])
    np.save('{}_histograms.npy'.format(JOB), load_histograms(JOB)[0]['buffers'])
    np.save('{}_opticalflow.npy'.format(JOB), load_opticalflow(JOB)[0]['buffers'])

# After running this, run:
# ffmpeg -safe 0 -f concat -i <(for f in ./*.mkv; do echo "file '$PWD/$f'"; done) -c copy output.mkv
def save_debug_video():
    bufs = load_output_buffers(JOB, 'video', lambda buf: buf)[0]['buffers']
    i = 0
    for buf in bufs:
        if len(buf) == 0: continue
        ext = 'mkv' if cv_version >= 3 else 'avi'
        with open('out_{:06d}.{}'.format(i, ext), 'wb') as f:
            f.write(buf)
        i += 1

def main():
    DATASET = sys.argv[2]
    JOB = sys.argv[1]
    for features in load_features(DATASET, JOB): pass
        #np.save('{}_{
    #for flow in load_opticalflow(DATASET, JOB):
    #    np.save('{}_{:06d}'.format(JOB, flow['index']), np.array(flow['buffers']))

if __name__ == "__main__":
    main()