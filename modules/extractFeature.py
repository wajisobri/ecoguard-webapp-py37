##-----------------------------------------------------------------------------
##  Import
##-----------------------------------------------------------------------------
from cv2 import imread
import os
from modules.segment import segment
from modules.normalize import normalize
from modules.encode import encode
from matplotlib import pyplot as plt
from datetime import datetime


##-----------------------------------------------------------------------------
##  Parameters for extracting feature
##	(The following parameters are default for CASIA1 dataset)
##-----------------------------------------------------------------------------
# Segmentation parameters
eyelashes_thres = 5

# Normalisation parameters
radial_res = 20
angular_res = 240

# Feature encoding parameters
minWaveLength = 18
mult = 1
sigmaOnf = 0.5


##-----------------------------------------------------------------------------
##  Function
##-----------------------------------------------------------------------------
def extractFeature(im_filename, eyelashes_thres=5, use_multiprocess=True):
	"""
	Description:
		Extract features from an iris image

	Input:
		im_filename			- The input iris image
		use_multiprocess	- Use multiprocess to run

	Output:
		template			- The extracted template
		mask				- The extracted mask
		im_filename			- The input iris image
	"""
	plt.rcParams["figure.figsize"] = [12, 7]
	plt.rcParams["figure.autolayout"] = True

	# Perform segmentation
	im = imread(im_filename, 0)
	ciriris, cirpupil, imwithnoise = segment(im, eyelashes_thres, use_multiprocess)

	plt.subplot(1, 3, 1)

	# Show image with ciriris and cirpupil
	plt.imshow(imwithnoise, cmap='gray')
	plt.axis('off')
	plt.title('Segmentation Result')
	# plt.show()

	# Perform normalization
	polar_array, noise_array = normalize(imwithnoise, ciriris[1], ciriris[0], ciriris[2],
										 cirpupil[1], cirpupil[0], cirpupil[2],
										 radial_res, angular_res)
	
	plt.subplot(1, 3, 2)

	# Show polar_array
	plt.imshow(polar_array, cmap='gray')
	plt.axis('off')
	plt.title('Normalization Result')
	# plt.show()

	# Perform feature encoding
	template, mask = encode(polar_array, noise_array, minWaveLength, mult, sigmaOnf)

	plt.subplot(1, 3, 3)

	# Show template
	plt.imshow(template, cmap='gray')
	plt.axis('off')
	plt.title('Encoding Result')

	# plt.show()

	# Save plot to image
	timestamp = datetime.now()
	filename = "plot_"+ timestamp.strftime("%Y%m%d%H%M%S") + ".jpg"
	plt.savefig(os.path.join('./temp/', filename))
	plt.close()

	# Return
	return template, mask, im_filename
