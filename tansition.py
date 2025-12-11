import subprocess

def generate_transition_segment(path="transition.ts", duration=5):
    cmd = [
        "ffmpeg",
        "-y",
        "-f", "lavfi",
        "-i", f"color=size=1280x720:rate=30:color=black",
        "-vf", f"fade=t=in:st=0:d=0.75,fade=t=out:st=0.75:d=0.75",
        "-t", str(duration),
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-pix_fmt", "yuv420p",
        "-f", "mpegts",
        path
    ]

    subprocess.run(cmd)
    return path

generate_transition_segment()