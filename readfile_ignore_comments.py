'''

   Code for reading file ignoring anything following an octothorp
   and any trailing whitespace after its removal

'''

def strip_string(commented_line, change_case):
    ''' Allow trailing comments by removing them, and optionally change case '''
    #   Parse option to change case

    if change_case == -1:
        commented_line = commented_line.lower()
    else:
        if change_case == 1:
            commented_line = commented_line.upper()

    # Only interested in the first item delimited by a #

    cleaved = commented_line.split("#")
    commented_line = cleaved[0].strip()

    return commented_line


#
#   If we can't find the file, return a [] and don't generate an exception
#


def readfile_ignore_comments(diskname, change_case):
    ''' Read file and trim newlines 'nd trailing comments '''
    try:
        #   read list of words to exclude
        with open(diskname,encoding='ascii') as parameter_file:
            exclude = parameter_file.readlines()
            parameter_file.close()

            # Remove all the pesky \n's

            exclude = [x.replace("\n", "") for x in exclude]

            # Make list case independent

#            for pos in range(len(exclude)):
#                exclude[pos] = strip_string(exclude[pos], change_case)

            print(exclude)

            for item in exclude:
                item = strip_string(item,change_case)



            # If theres now no string left, ignore it
            exclude = list(filter(None, exclude))

            return exclude

    except FileNotFoundError:
        return []

    except Exception as err:
        print(err)

    return []
