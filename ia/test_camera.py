import cv2

cap = cv2.VideoCapture(1)

if not cap.isOpened():
    print("Impossible d'ouvrir la webcam")
    exit()

while True:
    ret, frame = cap.read()

    if not ret:
        print("Impossible de lire l'image")
        break

    cv2.imshow("CyberJam Webcam", frame)

    if cv2.waitKey(1) & 0xFF == 27:  # ESC
        break

cap.release()
cv2.destroyAllWindows()