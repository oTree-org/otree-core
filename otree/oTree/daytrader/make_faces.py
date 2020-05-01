import cv2

"""
https://stackoverflow.com/questions/40895785/using-opencv-to-overlay-transparent-image-onto-another-image
"""

path = '../_static/daytrader/'
color_imgs = ['C0', 'C1', 'C2', 'C3', 'C4', 'C5', 'C6', 'C7', 'C8', 'C9']
faces = ['glad', 'sad']

for c in color_imgs:
    for face in faces:
        background = cv2.imread('{}{}{}'.format(path, c, '.png'), cv2.IMREAD_UNCHANGED)
        foreground = cv2.imread('{}{}{}'.format(path, face, '.png'), cv2.IMREAD_UNCHANGED)

        # normalize alpha channels from 0-255 to 0-1
        alpha_background = background[:,:,3] / 255.0
        alpha_foreground = foreground[:,:,3] / 255.0

        # set adjusted colors
        for color in range(0, 3):
            background[:,:,color] = alpha_foreground * foreground[:,:,color] + alpha_background * background[:,:,color] * (1 - alpha_foreground)

        # set adjusted alpha and denormalize back to 0-255
        background[:,:,3] = (1 - (1 - alpha_foreground) * (1 - alpha_background)) * 255

        # display the image (NOTE: any transparency will be shown as black on a screen)
        # cv2.imshow("Composited image", background)
        # cv2.waitKey(0)
        dst = '{}{}{}'.format(c, face, '.png')
        cv2.imwrite('{}{}'.format(path, dst), background)
