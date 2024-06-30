import daytime

# At some point set these up externally

daycrop = (750, 750 + 640, 400, 400 + 480)
nightcrop = (450, 1400, 480, 980)


def crop(image, daylight, daycrop, nightcrop):
    ''' Crop image in a daylight dependent way '''
    latitude = location[0]
    longitude = location[1]

    size_x = image.shape[0]
    size_y = image.shape[1]

    if size_x == 1080:
        if daylight:
            x_low = daycrop[0]
            x_high = daycrop[1]
            y_low = daycrop[2]
            y_high = daycrop[3]
        else:
            x_low = nightcrop[0]
            x_high = nightcrop[1]
            y_low = nightcrop[2]
            y_high = nightcrop[3]
    else:
        return image

    # Cropping an HD image

    cropped_image = image[y_low:y_high, x_low:x_high]

    return cropped_image

