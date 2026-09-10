from minimax_r2v.run import run_job as handler
import runpod

if __name__ == "__main__":
    runpod.serverless.start({"handler": handler})
