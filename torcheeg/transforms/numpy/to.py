from typing import Dict, Tuple, Union

from scipy.interpolate import griddata

import numpy as np

from ..base_transform import EEGTransform


class To2d(EEGTransform):
    r'''
    Taking the electrode index as the row index and the temporal index as the column index, a two-dimensional EEG signal representation with the size of [number of electrodes, number of data points] is formed. While PyTorch performs convolution on the 2d tensor, an additional channel dimension is required, thus we append an additional dimension.

    .. code-block:: python

        transform = To2d()
        transform(eeg=torch.randn(32, 128))['eeg'].shape
        >>> (1, 32, 128)

    .. automethod:: __call__
    '''
    def __call__(self,
                 *args,
                 eeg: np.ndarray,
                 baseline: Union[np.ndarray, None] = None,
                 **kwargs) -> Dict[str, np.ndarray]:
        r'''
        Args:
            eeg (np.ndarray): The input EEG signals in shape of [number of electrodes, number of data points].
            baseline (torch.Tensor, optional) : The corresponding baseline signal, if apply_to_baseline is set to True and baseline is passed, the baseline signal will be transformed with the same way as the experimental signal.

        Returns:
            np.ndarray: The transformed results with the shape of [1, number of electrodes, number of data points].
        '''
        return super().__call__(*args, eeg=eeg, baseline=baseline, **kwargs)

    def apply(self, eeg: np.ndarray, **kwargs) -> np.ndarray:
        return eeg[np.newaxis, ...]


class ToGrid(EEGTransform):
    r'''
    A transform method to project the EEG signals of different channels onto the grid according to the electrode positions to form a 3D EEG signal representation with the size of [number of data points, width of grid, height of grid]. For the electrode position information, please refer to constants grouped by dataset:

    - datasets.constants.emotion_recognition.deap.DEAP_CHANNEL_LOCATION_DICT
    - datasets.constants.emotion_recognition.dreamer.DREAMER_CHANNEL_LOCATION_DICT
    - datasets.constants.emotion_recognition.seed.SEED_CHANNEL_LOCATION_DICT
    - ...

    .. code-block:: python

        transform = ToGrid(DEAP_CHANNEL_LOCATION_DICT)
        transform(eeg=torch.randn(32, 128))['eeg'].shape
        >>> (128, 9, 9)

    Args:
        channel_location_dict (dict): Electrode location information. Represented in dictionary form, where :obj:`key` corresponds to the electrode name and :obj:`value` corresponds to the row index and column index of the electrode on the grid.
        apply_to_baseline: (bool): Whether to act on the baseline signal at the same time, if the baseline is passed in when calling. (defualt: :obj:`False`)
    
    .. automethod:: __call__
    '''
    def __init__(self,
                 channel_location_dict: Dict[str, Tuple[int, int]],
                 apply_to_baseline: bool = False):
        super(ToGrid, self).__init__(apply_to_baseline=apply_to_baseline)
        self.channel_location_dict = channel_location_dict
        loc_x_list = []
        loc_y_list = []
        for _, (loc_x, loc_y) in channel_location_dict.items():
            loc_x_list.append(loc_x)
            loc_y_list.append(loc_y)
        self.height = max(loc_y_list) + 1
        self.width = max(loc_x_list) + 1

    def __call__(self,
                 *args,
                 eeg: np.ndarray,
                 baseline: Union[np.ndarray, None] = None,
                 **kwargs) -> Dict[str, np.ndarray]:
        r'''
        Args:
            eeg (np.ndarray): The input EEG signals in shape of [number of electrodes, number of data points].
            baseline (torch.Tensor, optional) : The corresponding baseline signal, if apply_to_baseline is set to True and baseline is passed, the baseline signal will be transformed with the same way as the experimental signal.

        Returns:
            np.ndarray: The projected results with the shape of [number of data points, width of grid, height of grid].
        '''
        return super().__call__(*args, eeg=eeg, baseline=baseline, **kwargs)

    def apply(self, eeg: np.ndarray, **kwargs) -> np.ndarray:
        # electronode eeg timestep
        outputs = np.zeros([self.width, self.height, eeg.shape[-1]])
        # 9 eeg 9 eeg timestep
        for i, (loc_x, loc_y) in enumerate(self.channel_location_dict.values()):
            outputs[loc_x][loc_y] = eeg[i]

        outputs = outputs.transpose(2, 0, 1)
        # timestep eeg 9 eeg 9
        return outputs

    @property
    def repr_body(self) -> Dict:
        return dict(super().repr_body, **{
            'channel_location_dict': {...}
        })

class ToInterpolatedGrid(EEGTransform):
    r'''
    A transform method to project the EEG signals of different channels onto the grid according to the electrode positions to form a 3D EEG signal representation with the size of [number of data points, width of grid, height of grid]. For the electrode position information, please refer to constants grouped by dataset:

    - datasets.constants.emotion_recognition.deap.DEAP_CHANNEL_LOCATION_DICT
    - datasets.constants.emotion_recognition.dreamer.DREAMER_CHANNEL_LOCATION_DICT
    - datasets.constants.emotion_recognition.seed.SEED_CHANNEL_LOCATION_DICT
    - ...

    .. code-block:: python
    
        transform = ToInterpolatedGrid(DEAP_CHANNEL_LOCATION_DICT)
        transform(eeg=torch.randn(32, 128))['eeg'].shape
        >>> (128, 9, 9)

    Especially, missing values on the grid are supplemented using cubic interpolation

    Args:
        channel_location_dict (dict): Electrode location information. Represented in dictionary form, where :obj:`key` corresponds to the electrode name and :obj:`value` corresponds to the row index and column index of the electrode on the grid.
        apply_to_baseline: (bool): Whether to act on the baseline signal at the same time, if the baseline is passed in when calling. (defualt: :obj:`False`)

    .. automethod:: __call__
    '''
    def __init__(self,
                 channel_location_dict: Dict[str, Tuple[int, int]],
                 apply_to_baseline: bool = False):
        super(ToInterpolatedGrid,
              self).__init__(apply_to_baseline=apply_to_baseline)
        self.channel_location_dict = channel_location_dict
        self.location_array = np.array(list(channel_location_dict.values()))
        grid_x, grid_y = np.mgrid[
            min(self.location_array[:, 0]):max(self.location_array[:,
                                                                   0]):9 * 1j,
            min(self.location_array[:, 1]):max(self.location_array[:,
                                                                   1]):9 * 1j, ]
        self.grid_x = grid_x
        self.grid_y = grid_y

    def __call__(self,
                 *args,
                 eeg: np.ndarray,
                 baseline: Union[np.ndarray, None] = None,
                 **kwargs) -> Dict[str, np.ndarray]:
        r'''
        Args:
            eeg (np.ndarray): The input EEG signals in shape of [number of electrodes, number of data points].
            baseline (torch.Tensor, optional) : The corresponding baseline signal, if apply_to_baseline is set to True and baseline is passed, the baseline signal will be transformed with the same way as the experimental signal.
            
        Returns:
            np.ndarray: The projected results with the shape of [number of data points, width of grid, height of grid].
        '''
        return super().__call__(*args, eeg=eeg, baseline=baseline, **kwargs)

    def apply(self, eeg: np.ndarray, **kwargs) -> np.ndarray:
        # channel eeg timestep
        eeg = eeg.transpose(1, 0)
        # timestep eeg channel
        outputs = []
        for timestep_split_x in eeg:
            outputs.append(
                griddata(self.location_array,
                         timestep_split_x, (self.grid_x, self.grid_y),
                         method='cubic',
                         fill_value=0))
        outputs = np.array(outputs)
        return outputs

    @property
    def repr_body(self) -> Dict:
        return dict(super().repr_body, **{
            'channel_location_dict': {...}
        })