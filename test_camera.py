import depthai as dai

# Create pipeline
pipeline = dai.Pipeline()

# Add a color camera
cam = pipeline.createColorCamera()
cam.setPreviewSize(640, 480)
cam.setInterleaved(False)

# Create an output stream to host
xout = pipeline.createXLinkOut()
xout.setStreamName("video")
cam.preview.link(xout.input)

# Connect to device
with dai.Device(pipeline) as device:
    print("🎥 DepthAI device connected. Streaming frames... (Press Ctrl+C to stop)")

    q = device.getOutputQueue(name="video", maxSize=4, blocking=False)

    while True:
        in_frame = q.get()
        frame = in_frame.getCvFrame()
        print("✅ Got frame:", frame.shape)
