# from flask import Flask, Response
# import depthai as dai
# import cv2
#
# app = Flask(__name__)
#
# # 🎥 Setup DepthAI pipeline
# pipeline = dai.Pipeline()
# cam = pipeline.createColorCamera()
# cam.setPreviewSize(640, 480)
# cam.setInterleaved(False)
#
# # Output stream
# xout = pipeline.createXLinkOut()
# xout.setStreamName("video")
# cam.preview.link(xout.input)
#
# # 🛠 Connect to device ONCE
# device = dai.Device(pipeline)
# print("✅ DepthAI camera initialized!")
#
# queue = device.getOutputQueue(name="video", maxSize=4, blocking=False)
#
# # 🔄 Frame generator for MJPEG stream
# def generate_frames():
#     while True:
#         in_frame = queue.get()
#         frame = in_frame.getCvFrame()
#
#         # Encode frame as JPEG
#         ret, buffer = cv2.imencode('.jpg', frame)
#         if not ret:
#             continue
#
#         # Convert to bytes
#         frame_bytes = buffer.tobytes()
#
#         # Yield in HTTP multipart format
#         yield (b'--frame\r\n'
#                b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
#
# # 🌐 Flask route for MJPEG stream
# @app.route('/video_feed')
# def video_feed():
#     return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')
#
# # ✅ Home route for testing
# @app.route('/')
# def index():
#     return '<h1>DepthAI Camera Live Stream</h1><img src="/video_feed" width="640">'
#
# if __name__ == '__main__':
#     app.run(host='0.0.0.0', port=8080, debug=False)
