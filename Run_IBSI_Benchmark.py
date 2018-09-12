#!/usr/bin/env python
import logging
import os

import numpy as np
import pandas as pd
import SimpleITK as sitk

import radiomics
from radiomics import setVerbosity, featureextractor

if not os.path.isdir("results"):
  os.mkdir("results")

CASES = range(1, 6)
TYPES = ['', '_Combined']
IBSI_RESAMPLING = True

#"""
rLogger = radiomics.logger
logHandler = logging.FileHandler(filename='results/IBSIlog.log', mode='w')
logHandler.setLevel(logging.DEBUG)
logHandler.setFormatter(logging.Formatter('%(levelname)-.1s: %(name)s: %(message)s'))

rLogger.setLevel(logging.DEBUG)
rLogger.addHandler(logHandler)

setVerbosity(logging.INFO)
# """

ibsiLogger = logging.getLogger('radiomics.ibsi')


def run_phantom():
  ibsiLogger.info('################################### Extracting Phantom #############################')
  extractor = featureextractor.RadiomicsFeaturesExtractor()

  image = sitk.ReadImage(os.path.join('Data', 'Digital Phantom', 'Phantom.nrrd'))
  mask = sitk.ReadImage(os.path.join('Data', 'Digital Phantom', 'Phantom-label.nrrd'))

  result_series = pd.Series()
  extraction_mode = ('2D', '3D')
  for e in extraction_mode:
    ibsiLogger.info('######################### MODE %s ####################' % e)
    for t in TYPES:
      ibsiLogger.info('######################### TYPE %s ####################' % t)
      params = os.path.join('Configuration', 'Phantom%s.yml' % t)
      if not os.path.isfile(params):
        continue
      extractor.loadParams(params)
      extractor.addProvenance(provenance_on=(t == ''))
      extractor.settings['interpolator'] = None
      extractor.settings['force2D'] = e == '2D'

      fv = pd.Series(extractor.execute(image, mask))

      if t != '':
        fv = fv.add_prefix(t[1:] + '_')

      if extractor.settings.get('force2D', False):
        fv = fv.add_prefix('2D_')
      else:
        fv = fv.add_prefix('3D_')
      result_series = result_series.append(fv)

    result_series.name = 'phantom'
    #result_series.to_csv('resCase%d.csv' % case_idx)  # Uncomment to enable saving intermediate results
  return result_series

def run_case(case_idx, image, mask):
  ibsiLogger.info('################################### Extracting Case %d #############################' % case_idx)
  extractor = featureextractor.RadiomicsFeaturesExtractor()

  if IBSI_RESAMPLING:
    if case_idx == 1:
      pass
    elif case_idx == 2:
      image, mask = IBSI_resampling(image, mask, (2, 2, 0), 0)
    elif case_idx == 5:
      image, mask = IBSI_resampling(image, mask, (2, 2, 2), 0, interpolator=sitk.sitkBSpline)
    else:
      image, mask = IBSI_resampling(image, mask, (2, 2, 2), 0)

  result_series = pd.Series()
  for t in TYPES:
    ibsiLogger.info('######################### TYPE %s ####################' % t)
    params = os.path.join('Configuration', 'case%d%s.yml' % (case_idx, t))
    if not os.path.isfile(params):
      continue
    extractor.loadParams(params)
    extractor.addProvenance(provenance_on=(t == ''))

    fv = pd.Series(extractor.execute(image, mask))

    if t != '':
      fv = fv.add_prefix(t[1:] + '_')

    if extractor.settings.get('force2D', False):
      fv = fv.add_prefix('2D_')
    else:
      fv = fv.add_prefix('3D_')
    result_series = result_series.append(fv)

  result_series.name = case_idx
  #result_series.to_csv('resCase%d.csv' % case_idx)  # Uncomment to enable saving intermediate results
  return result_series


def IBSI_resampling(image, mask, spacing, grayValuePrecision=None, interpolator=sitk.sitkLinear):
  # resample image to new spacing, align centers of both resampling grids.

  im_spacing = np.array(image.GetSpacing(), dtype='float')
  im_size = np.array(image.GetSize(), dtype='float')

  spacing = np.where(np.array(spacing) == 0, im_spacing, spacing)

  spacingRatio = im_spacing / spacing
  newSize = np.ceil(im_size * spacingRatio)

  # Calculate center in real-world coordinates
  im_center = image.TransformContinuousIndexToPhysicalPoint((im_size - 1) / 2)

  new_origin = tuple(np.array(image.GetOrigin()) + 0.5 * ((im_size - 1) * im_spacing - (newSize - 1) * spacing))

  ibsiLogger.info('Resampling from %s to %s (size %s to %s), aligning Centers', im_spacing, spacing, im_size, newSize)

  rif = sitk.ResampleImageFilter()
  rif.SetOutputOrigin(new_origin)
  rif.SetSize(np.array(newSize, dtype='int').tolist())
  rif.SetOutputDirection(image.GetDirection())
  rif.SetOutputSpacing(spacing)

  rif.SetOutputPixelType(sitk.sitkFloat32)
  rif.SetInterpolator(interpolator)
  res_im = rif.Execute(sitk.Cast(image, sitk.sitkFloat32))

  grayValuePrecision = None
  # Round to n decimals (0 = to nearest integer)
  if grayValuePrecision is not None:
    ibsiLogger.debug('Rounding Image Gray values to %d decimals', grayValuePrecision)
    im_arr = sitk.GetArrayFromImage(res_im)
    im_arr = np.round(im_arr, grayValuePrecision)
    round_im = sitk.GetImageFromArray(im_arr)
    round_im.CopyInformation(res_im)
    res_im = round_im

  # Sanity check: Compare Centers!
  new_center = res_im.TransformContinuousIndexToPhysicalPoint((newSize - 1) / 2)
  ibsiLogger.debug("diff centers: %s" % np.abs(np.array(im_center) - np.array(new_center)))

  rif.SetOutputPixelType(sitk.sitkFloat32)
  rif.SetInterpolator(sitk.sitkLinear)
  res_ma = rif.Execute(sitk.Cast(mask, sitk.sitkFloat32))
  res_ma = sitk.BinaryThreshold(res_ma, lowerThreshold=0.5)

  return res_im, res_ma


def index_func(series, *args, **kwargs):
  if 'idx' not in series or np.isnan(series['idx']):
    return series

  idx_loc = series.index.get_loc('idx')

  vals = []
  for val in series.iloc[idx_loc+1:]:
    vals.append(val)

  for val_idx, value in enumerate(vals):
    try:
      # new_val = eval(value)
      series.values[int(idx_loc + 1 + val_idx)] = value[int(series['idx'])]
    except:
      pass
  return series


if __name__ == '__main__':
  im = sitk.ReadImage(os.path.join('Data', 'Patient Cases', 'PAT1', 'PAT1.nrrd'))
  ma = sitk.ReadImage(os.path.join('Data', 'Patient Cases', 'PAT1', 'GTV.nrrd'))

  rif = sitk.ResampleImageFilter()
  rif.SetReferenceImage(im)
  rif.SetInterpolator(sitk.sitkNearestNeighbor)
  rif.SetOutputPixelType(ma.GetPixelID())
  ma = rif.Execute(ma)

  mapping_file = os.path.join('Data', 'Benchmark', 'mapping_phantom.csv')
  mapping = pd.read_csv(mapping_file)

  results = mapping.join(run_phantom(), on='pyradiomics_feature', how='left')
  results = results.apply(index_func, axis=1)

  results.sort_index(inplace=True)
  results.to_csv('results/results_phantom.csv')

  for case in CASES:
    mapping_file = os.path.join('Data', 'Benchmark', 'mapping_case%s.csv' % case)
    mapping = pd.read_csv(mapping_file)

    results = mapping.join(run_case(case, im, ma), on='pyradiomics_feature', how='left')
    results = results.apply(index_func, axis=1)

    results.sort_index(inplace=True)
    results.to_csv('results/results_case%s.csv' % case)
  exit(0)
