from matplotlib.path import Path
import torch
import os
from torch import nn
from torch.utils.data import DataLoader
from torch.utils.data import Dataset
import numpy as np
import cv2


class skyDataset(Dataset):
    def __init__(self, dataset_dim, data_path, label_path):
        super().__init__()
        self.image_w = 125
        self.data = np.memmap(data_path, dtype='float32', mode='r', shape=(dataset_dim, 3, self.image_w, self.image_w))
        self.label = np.memmap(label_path, dtype='uint8', mode='r', shape=(dataset_dim,))
        self.size = dataset_dim

    def __len__(self):
        return self.size

    def __getitem__(self, idx):
        image = self.data[idx]
        image = torch.from_numpy(np.array(image))

        label = torch.tensor(self.label[idx], dtype=torch.float32)

        return image, label


class skyModel(nn.Module):
    def __init__(self):
        super(skyModel, self).__init__()

        self.conv1 = nn.Conv2d(3, 3, 5, 4)  # 5x5 con stride 4
        self.conv2 = nn.Conv2d(3, 3, 3, 2)  # 3x3 con stride 2
        self.relu = nn.ReLU()
        self.fc = nn.Linear(675, 1)

        self.imgSize=125

        #to be updated in case of retraining
        self.means = np.array([147.79283, 163.6854, 182.02965])
        self.stds = np.array([43.91934, 34.63735, 31.404087])

    def forward(self, x):
        x = self.conv1(x)
        x = self.relu(x)
        x = self.conv2(x)
        x = self.relu(x)
        x = x.reshape(-1,675)
        x = self.fc(x)
        x = torch.sigmoid(x)
        return x

    
    def evaluatePicture(self, original_image: np.ndarray):
        """Any picture format can be used as input. It returns 0 if it won't rain, 1 otherwise."""
        #let's take a central square picture from this image sized (self.imgSize, self.imgSize)
        input_h, input_w = original_image.shape[:2]
        square_width = min(input_w,input_h)
        offset_height = (input_h - square_width) // 2
        offset_width = (input_w - square_width) // 2

        image = original_image[offset_height:offset_height+square_width, offset_width:offset_width+square_width,:]
        
        new_dim = (self.imgSize, self.imgSize)
        resized = cv2.resize(image, new_dim, interpolation = cv2.INTER_AREA)

        #let's put axis in the right order + apply normalization
        resized = torch.from_numpy(resized)
        img = resized.to(dtype=torch.float32)
        img = torch.moveaxis(img,-1,0)
        for i in range(3):
            img[i,:,:] = (img[i,:,:] - self.means[i])/self.stds[i]

        #now let's evaluate this picture.

        #let's put it in a batch
        img = img.unsqueeze(0)

        y_pred = self(img)
        y_pred = torch.round(y_pred)

        #it will return 0 if it won't rain, 1 if it will rain.
        res = 1 if y_pred[0][0] else 0 
        return res

    def evaluatePictureFromPath(self, path_to_image : str):
        """Any picture format can be used as input. It returns 0 if it won't rain, 1 otherwise."""
        img = cv2.imread(path_to_image)
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        return self.evaluatePicture(img)



