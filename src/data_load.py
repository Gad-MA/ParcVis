from importlib_resources import files

import numpy as np
import nibabel as nib

from scipy.ndimage import convolve1d


def load_images(
    nifti_path,
    anat_path=None,
    thr: float = None,
    normalize: bool = False,
    components: list = None,
):
    nifti = nib.load(nifti_path)
    nifti_affine = nifti.affine
    nifti_data = nifti.get_fdata()

    if anat_path is None:
        anat_path = files("src.data").joinpath("mni_template.nii.gz")
    anat = nib.load(anat_path)
    anat_affine = anat.affine
    anat_data = anat.get_fdata()

    whole_mask = nifti_data == 0.0
    if len(whole_mask.shape) == 4:
        combined_mask = np.all(whole_mask, axis=-1)
    else:
        combined_mask = whole_mask

    if len(nifti_data.shape) == 3:
        nifti_data = nifti_data.astype(int)

        features = np.unique(nifti_data).astype(int)
        labels = features[features != 0]

        new_nifti_data = np.zeros((*nifti_data.shape, len(labels)))

        if components is not None:
            missing = [c for c in components if c not in labels]
            assert (
                len(missing) == 0
            ), f"Provided components {missing} are not present in the nifti labels"
            target_components = set(components)
        else:
            target_components = set(labels)

        kernel = np.ones((5)) / 5
        for idx, lbl in enumerate(labels):
            if lbl in target_components:
                roi_data = (nifti_data == lbl).astype(float)
                for j in range(3):
                    roi_data = convolve1d(roi_data, kernel, axis=j)
            else:
                roi_data = np.zeros(nifti_data.shape)

            new_nifti_data[:, :, :, idx] = roi_data

        nifti_data = new_nifti_data

    if components is not None:
        features_after = np.unique(nifti_data, axis=None) if nifti_data.ndim == 4 else None
        labels_list = []
        for k in range(nifti_data.shape[-1]):
            vol = nifti_data[:, :, :, k]
            if np.any(vol > 0):
                pos = np.argwhere(vol > 0)
                if pos.size > 0:
                    labels_list.append(None)
                else:
                    labels_list.append(None)
            else:
                labels_list.append(None)

        comp_arr = np.array(components)
        if np.all((comp_arr >= 1) & (comp_arr <= nifti_data.shape[-1])):
            comp_idx = comp_arr.astype(int) - 1
        else:
            raise AssertionError(
                "Cannot map provided components to available data axes. "
                "Provide components as indices (1-based) matching the 4th axis "
                "or use labels that are exactly the consecutive sorted labels present in the nifti."
            )
        nifti_data = nifti_data[:, :, :, comp_idx]

    if normalize:
        mask_idx = np.where(~combined_mask)
        mask_slices = tuple([idx for idx in mask_idx])
        S = nifti_data[mask_slices + (slice(None),)]

        S = S - np.median(S, axis=0)

        S = (np.diag(1 / np.abs(S.T).max(axis=1)) @ S.T).astype("float32")

        midx = np.argmax(np.abs(S), axis=1)
        signs = np.diag(S[np.arange(S.shape[0]), midx])
        S = signs @ S

        S = S.T
        nifti_data[mask_slices + (slice(None),)] = S

        combined_mask = np.stack([combined_mask] * nifti_data.shape[-1], axis=-1)
        nifti_data = np.ma.masked_array(nifti_data, mask=combined_mask)

    if thr is not None:
        nifti_data = np.ma.masked_inside(nifti_data, -thr, thr, copy=False)

    return nifti_data, nifti_affine, anat_data, anat_affine
