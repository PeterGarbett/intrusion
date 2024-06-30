import daytime


def crop(image, daylight, daycrop, nightcrop):
    """Crop image in a daylight dependent way"""

    size_x = image.shape[0]
    size_y = image.shape[1]

    if daylight:

        if daycrop is not None:
            x_low = daycrop[0]
            x_high = daycrop[1]
            y_low = daycrop[2]
            y_high = daycrop[3]
        else:
            return image
    else:
        if nightcrop is not None:
            x_low = nightcrop[0]
            x_high = nightcrop[1]
            y_low = nightcrop[2]
            y_high = nightcrop[3]
        else:
            return image

    # Cropping image

    cropped_image = image[y_low:y_high, x_low:x_high]

    return cropped_image
