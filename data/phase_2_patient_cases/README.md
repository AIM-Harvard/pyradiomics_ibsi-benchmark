Data provided in patient cases consists of the image and 2 nearly identical segmentations:
The GTV.nrrd is as provided by Alex Zwanenburg (converted by their in-house tools DICOM RT STRUCT)
The GTV_plastimatch is the GTV as converted to a binary label map by plastimatch.

Between the 2 segmentations, there is 1 voxel different (included in plastimatch conversion, excluded by Alex Zwanenburgs' conversion).
This pixel is located at (x, y, z): (139, 101, 40), with origin defined as (0, 0, 0).

For the conversion of the image from DICOM, Nrrdify (github.com/JoostJM/nrrdify.git) was used. The result of this conversion was identical
to the niftii provided by Alex Zwanenburg (converted by in-house software).
