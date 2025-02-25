### Mode 1 stretch is based on C code provided by a fellow astronomy enthusiast

import time
import numpy
import logging


logger = logging.getLogger('indi_allsky')


class IndiAllSkyStretch(object):

    def __init__(self, config, bin_v, night_v, moonmode_v, mask=None):
        self.config = config

        self.bin_v = bin_v
        self.night_v = night_v
        self.moonmode_v = moonmode_v

        self._sqm_mask = mask

        self._numpy_mask = None


    def main(self, data, image_bit_depth):
        if isinstance(self._numpy_mask, type(None)):
            # This only needs to be done once
            self._generateNumpyMask(data)


        if self.night_v.value:
            # night
            if self.moonmode_v.value and not self.config.get('IMAGE_STRETCH', {}).get('MOONMODE'):
                logger.info('Moon mode stretching disabled')
                return data, False
        else:
            # daytime
            if not self.config.get('IMAGE_STRETCH', {}).get('DAYTIME'):
                return data, False


        if self.config.get('IMAGE_STRETCH', {}).get('MODE1_ENABLE'):
            logger.info('Using image stretch mode 1')
            return self.mode1_stretch(data, image_bit_depth), True
        else:
            logger.info('Image stretching disabled')
            return data, False


    def mode1_stretch(self, data, image_bit_depth):

        data = self.mode1_apply_gamma(data, image_bit_depth)

        data = self.mode1_adjustImageLevels(data, image_bit_depth)

        return data


    def mode1_apply_gamma(self, data, image_bit_depth):
        gamma = self.config.get('IMAGE_STRETCH', {}).get('MODE1_GAMMA', 3.0)

        if not gamma:
            return data

        logger.info('Applying gamma correction')

        gamma_start = time.time()

        if image_bit_depth == 8:
            data_max = 256
            range_array = numpy.arange(0, data_max, dtype=numpy.float32)
            lut = (((range_array / data_max) ** (1 / float(gamma))) * data_max).astype(numpy.uint8)
        else:
            data_max = 2 ** image_bit_depth
            range_array = numpy.arange(0, data_max, dtype=numpy.float32)
            lut = (((range_array / data_max) ** (1 / float(gamma))) * data_max).astype(numpy.uint16)


        # apply lookup table
        gamma_data = lut.take(data, mode='raise')

        gamma_elapsed_s = time.time() - gamma_start
        logger.info('Image gamma in %0.4f s', gamma_elapsed_s)

        return gamma_data


    def mode1_adjustImageLevels(self, data, image_bit_depth):
        stddevs = self.config.get('IMAGE_STRETCH', {}).get('MODE1_STDDEVS', 3.0)

        mean, stddev = self._get_image_stddev(data)
        logger.info('Mean: %0.2f, StdDev: %0.2f', mean, stddev)


        levels_start = time.time()

        data_max = 2 ** image_bit_depth

        low = int(mean - (stddevs * stddev))

        lowPercent  = (low / data_max) * 100
        highPercent = 100.0

        lowIndex = int((lowPercent / 100) * data_max)
        highIndex = int((highPercent / 100) * data_max)


        if image_bit_depth == 8:
            range_array = numpy.arange(0, data_max, dtype=numpy.float32)

            #range_array[range_array <= lowIndex] = 0
            #range_array[range_array > data_max] = data_max

            lut = (((range_array - lowIndex) * data_max) / (highIndex - lowIndex))  # floating point math, results in negative numbers

            lut[lut < 0] = 0  # clip low end
            lut[lut > data_max] = data_max  # clip high end

            lut = lut.astype(numpy.uint8)
        else:
            range_array = numpy.arange(0, data_max, dtype=numpy.float32)

            #range_array[range_array <= lowIndex] = 0
            #range_array[range_array > highIndex] = data_max

            lut = (((range_array - lowIndex) * data_max) / (highIndex - lowIndex))  # floating point math, results in negative numbers

            lut[lut < 0] = 0  # clip low end
            lut[lut > data_max] = data_max  # clip high end

            lut = lut.astype(numpy.uint16)


        # apply lookup table
        stretch_image = lut.take(data, mode='raise')

        levels_elapsed_s = time.time() - levels_start
        logger.info('Image levels in %0.4f s', levels_elapsed_s)


        return stretch_image


    def _get_image_stddev(self, data):
        mean_std_start = time.time()


        # mask arrays allow using the detection mask to perform calculations on
        # arbitrary boundaries in the image
        if len(data.shape) == 2:
            ma = numpy.ma.masked_array(data, mask=self._numpy_mask)

            # mono
            mean = numpy.ma.mean(ma)
            stddev = numpy.ma.std(ma)
        else:
            # color
            b_ma = numpy.ma.masked_array(data[:, :, 0], mask=self._numpy_mask)
            g_ma = numpy.ma.masked_array(data[:, :, 1], mask=self._numpy_mask)
            r_ma = numpy.ma.masked_array(data[:, :, 2], mask=self._numpy_mask)

            b_mean = numpy.ma.mean(b_ma)
            g_mean = numpy.ma.mean(g_ma)
            r_mean = numpy.ma.mean(r_ma)

            b_stddev = numpy.ma.std(b_ma)
            g_stddev = numpy.ma.std(g_ma)
            r_stddev = numpy.ma.std(r_ma)

            mean = (b_mean + g_mean + r_mean) / 3
            stddev = (b_stddev + g_stddev + r_stddev) / 3


        mean_std_elapsed_s = time.time() - mean_std_start
        logger.info('Mean and std dev in %0.4f s', mean_std_elapsed_s)

        return mean, stddev


    def _generateNumpyMask(self, img):
        if isinstance(self._sqm_mask, type(None)):
            logger.info('Generating mask based on SQM_ROI')

            image_height, image_width = img.shape[:2]

            mask = numpy.full((image_height, image_width), True, dtype=numpy.bool_)

            sqm_roi = self.config.get('SQM_ROI', [])

            try:
                x1 = int(sqm_roi[0] / self.bin_v.value)
                y1 = int(sqm_roi[1] / self.bin_v.value)
                x2 = int(sqm_roi[2] / self.bin_v.value)
                y2 = int(sqm_roi[3] / self.bin_v.value)
            except IndexError:
                logger.warning('Using central ROI for blob calculations')
                x1 = int((image_width / 2) - (image_width / 3))
                y1 = int((image_height / 2) - (image_height / 3))
                x2 = int((image_width / 2) + (image_width / 3))
                y2 = int((image_height / 2) + (image_height / 3))


            # True values will be masked
            mask[y1:y2, x1:x2] = False

        else:
            # True values will be masked
            mask = self._sqm_mask == 0


        self._numpy_mask = mask

