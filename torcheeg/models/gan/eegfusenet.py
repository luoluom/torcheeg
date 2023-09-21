import torch.nn as nn
import torch.nn.functional as F
import torch

class EEGfuseNet(nn.Module):
    r'''
    EEGFuseNet: A hybrid unsupervised network which can fuse high-dimensional EEG to obtain deep feature characterization and generate similar signals. For more details, please refer to the following information.

    - Paper: Z. Liang, R. Zhou, L. Zhang, L. Li, G. Huang, Z. Zhang, and S. Ishii, EEGFuseNet: Hybrid Unsupervised Deep Feature Characterization and Fusion for High-Dimensional EEG With an #Application to Emotion Recognition, IEEE Transactions on Neural Systems and Rehabilitation Engineering, 29, pp. 1913-1925, 2021.
    - URL: https://github.com/KAZABANA/EEGfusenet

    .. code-block:: python
        g_model=EEGfuseNet(in_channels=20,hidden_dim=16,n_layers=1,n_filters=1,chunk_size=128)
        X = torch.rand(128,20,128)
        fake_X,deep_feature=g_model(X)

    Args:
        in_channels (int): The input feature dimension. (default: :obj:`128`)
        hidden_dim  (int): Hidden dim of BI-GRU. (default: :obj:`16`)
        n_layers (int): The number of layers of BI-GRU. (default: :obj:`1`)
        n_filters (int): The number of filters of CNN based encoder. (default: :obj:`1`)
        chunk_size (int): Number of data points included in each EEG chunk.the size of the input EEG signal is( batch size × Channel × Time) (default: :obj:`128`)
    '''
    def __init__(self,
                    in_channels: int = 32,
                    hidden_dim: int = 16,
                    n_layers: int = 1,
                    n_filters: int = 1,
                    chunk_size:int = 384 ):  
        super(EEGfuseNet, self).__init__()
        
        
        self.n_filters = n_filters
        self.hidden_dim =  hidden_dim
        self.length = chunk_size/32

        self.conv1 = nn.Conv2d(1, 16*n_filters, (1, int(chunk_size/2+1)),stride = 1, padding = (0,int(chunk_size/4)))
        self.batchNorm1 = nn.BatchNorm2d(16*n_filters, False)
        
        self.depthwiseconv2 = nn.Conv2d(16*n_filters,32*n_filters,(in_channels,1),padding = 0)
        self.batchNorm2 = nn.BatchNorm2d(32*n_filters,False)
        self.pooling1 = nn.MaxPool2d((1,4),return_indices =True,ceil_mode=True)
    
        self.separa1conv3 = nn.Conv2d(32*n_filters,32*n_filters,(1, int(chunk_size/8+1)),
                                        stride=1,
                                        padding=(0,int(chunk_size/16)),
                                        groups=int(32*n_filters)) 
        self.separa2conv4 = nn.Conv2d(32*n_filters,16*n_filters,1) 
        self.batchNorm3 = nn.BatchNorm2d(16*n_filters,False)
        self.pooling2 = nn.MaxPool2d((1,8), 
                                        return_indices =True,
                                        ceil_mode=True)
        self.dropout1 = nn.Dropout(p=0.25)
        self.dropout2 = nn.Dropout(p=0.25)
        self.dropout3 = nn.Dropout(p=0.25)
        self.dropout4 = nn.Dropout(p=0.25)
        self.fc1 = nn.Linear(16*n_filters,16*n_filters)
        
        self.fc2 = nn.Linear(hidden_dim*2*n_filters,
                                hidden_dim*n_filters)
        
        self.fc3 = nn.Linear(hidden_dim*n_filters,
                                hidden_dim*2*n_filters)
        
        self.fc4 = nn.Linear(2*16*n_filters,
                                16*n_filters)

        self.gru_en = nn.GRU(16*n_filters,hidden_dim*n_filters,n_layers,
                                batch_first=True,
                                bidirectional=True)
        
        self.gru_de = nn.GRU(2*hidden_dim*n_filters,16*n_filters,n_layers,
                                batch_first=True,
                                bidirectional=True)
        
        self.lstm = nn.LSTM(16*n_filters,hidden_dim*n_filters,n_layers,
                            batch_first=True,
                            bidirectional=True)

        self.unpooling2 = nn.MaxUnpool2d((1, 8))
        self.batchnorm4 = nn.BatchNorm2d(32*n_filters,False)
        self.desepara2conv4 =  nn.ConvTranspose2d(16*n_filters,32*n_filters,1)
        self.desepara1conv3 =  nn.ConvTranspose2d( 32*n_filters, 32*n_filters, (1, int(chunk_size/8+1)),
                                                    stride=1,
                                                    padding=(0,int(chunk_size/16)),
                                                    groups= 32*n_filters )
    
        self.unpooling1 = nn.MaxUnpool2d((1, 4))
        self.batchnorm5 = nn.BatchNorm2d(16*n_filters, False)#
        self.dedepthsepara1conv3 = nn.ConvTranspose2d(32*n_filters,16*n_filters, 
                                                      (in_channels, 1), 
                                                      stride= 1, 
                                                      padding=0)
        self.deconv1 = nn.ConvTranspose2d(16*n_filters, 1, (1, int(chunk_size/2+1)), 
                                            stride = 1, 
                                            padding =(0,int(chunk_size/4)))
    def forward(self,x):
        r'''
        Args:
            x (torch.Tensor): EEG signal representation, the ideal input shape is :obj:`[n, 32, 384]`. Here, :obj:`n` corresponds to the batch size, :obj:`32` corresponds to :obj:`num_electrodes`, and :obj:`384` corresponds to :obj:`chunk_size`.

        Returns:
            torch.Tensor[size of batch, number of electrodes, length of EEG signal]，torch.Tensor[size of batch, length of deep feature code]: The first value is generated EEG signals. The second value is batch of extracted deep features,which used in the unsupervised EEG decoding, can represent the entire input EEG signals \ cross time points covering not only the EEG characteristics but also the EEG characteristics in the sequential information.
        '''
        x = x.unsqueeze(1)

        x = self.conv1(x)
        x = self.batchNorm1(x)
        
        x = self.depthwiseconv2(x)
        x = self.batchNorm2(x)       
        x = F.elu(x)
        end_dim1 = x.shape[-1]
        x,idx1 = self.pooling1(x)  
        x = self.dropout1(x)
        x = self.separa1conv3(x)     
        x = self.separa2conv4(x) 

        x = self.batchNorm3(x)
        x = F.elu(x)
        end_dim2 = x.shape[-1]
        x,idx2 = self.pooling2(x)

        x = x.permute(0,3,2,1)
        x = x[:,:,-1,:,]
        x = self.fc1(x)
        x = F.elu(x)
        out,_ = self.gru_en(x)
        x = out
        x = self.fc2(x)
        code = x.reshape((x.shape[0],-1)) 
        x = self.fc3(x)
        x,_ = self.gru_de(x)
    
        x = self.fc4(x)
        x = F.elu(x)
        x = x.reshape((x.shape[0],x.shape[1],1,x.shape[2]))
        x = x.permute(0,3,2,1)
        
        x = self.unpooling2(x, idx2)
        x = x[:,:,:,:end_dim2]

        x = self.desepara2conv4(x)
        x = self.desepara1conv3(x)
        x = self.batchnorm4(x)
        x = self.dropout4(x)
        
        x = F.elu(x)   
        x = self.unpooling1(x, idx1)  
        x = x[:,:,:,:end_dim1]    
        x = self.dedepthsepara1conv3(x)
        x = self.batchnorm5(x)

        x = self.deconv1(x)
        x = x.squeeze(1)
        return x,code

class EFDiscriminator(nn.Module):
    r'''
    EFDiscriminator: the discriminator that comes with EEGFuseNet is to distinguish whether the input EEG signals is a fake one generated by the eegfusenet or a real one collected from human brain.

    - Paper: Z. Liang, R. Zhou, L. Zhang, L. Li, G. Huang, Z. Zhang, and S. Ishii, EEGFuseNet: Hybrid Unsupervised Deep Feature Characterization and Fusion for High-Dimensional EEG With an #Application to Emotion Recognition, IEEE Transactions on Neural Systems and Rehabilitation Engineering, 29, pp. 1913-1925, 2021.
    - URL: https://github.com/KAZABANA/EEGfusenet

    .. code-block:: python
        g_model=EEGfuseNet(in_channels=20,hidden_dim=16,n_layers=1,n_filters=1,chunk_size=128)
        d_model = EFDiscriminator(in_channels=20,n_layers=1,n_filters=1,chunk_size=128)
        X = torch.rand(128,20,128)
        fake_X,deep_feature=g_model(X)
        p_real,p_fake = d_model(X),d_model(fake_X)

    Args:
        in_channels (int): The input feature dimension. (default: :obj:`128`)
        n_layers (int): The number of layers of BI-GRU. (default: :obj:`1`)
        n_filters (int): The number of filters in CNN based encoder. (default: :obj:`1`)
        chunk_size (int): Number of data points included in each EEG chunk. (default: :obj:`128`)
    '''
    def __init__(self,
                    in_channels:int = 32,
                    n_layers:int = 1,
                    n_filters:int = 1,
                    chunk_size:int = 384):
        super(EFDiscriminator, self).__init__()
        self.conv1 = nn.Conv2d(1, 8*n_filters, (1, int(chunk_size/2+1)),
                                stride = 1,
                                padding = 'same')
        self.batchNorm1 =nn.BatchNorm2d(8*n_filters, False)
        self.length=chunk_size/32

       
        self.depthwiseconv2 = nn.Conv2d(8* n_filters, 16*n_filters ,(in_channels,1), padding = 0)  
        self.batchNorm2 = nn.BatchNorm2d( 16*n_filters, False )
        self.pooling1 = nn.MaxPool2d((1,4),
                                        return_indices=False ,
                                        ceil_mode = True)

        self.separa1conv3 = nn.Conv2d(16*n_filters, 16*n_filters,
                                        (1, int(chunk_size/8+1)),
                                        stride=1,padding='same',
                                        groups=16*n_filters )

        self.separa2conv4 = nn.Conv2d(16*n_filters,8*n_filters,1) 
        self.batchNorm3 = nn.BatchNorm2d(8*n_filters,False)
        self.pooling2 = nn.MaxPool2d((1,8), return_indices = False)
        self.fc1 = nn.Linear(int(self.length)*8*n_filters,1)
    
    def forward(self,x):
        r'''
        Args:
            x (torch.Tensor): EEG signal representation or the fake generated EEGsignal, the size of the input EEG signal is( batch size × Channel × Time) whose ideal input shape is :obj:`[n, 32, 384]`. Here, :obj:`n` corresponds to the batch size, :obj:`32` corresponds to :obj:`num_electrodes`, and :obj:`384` corresponds to :obj:`chunk_size`.

        Returns:
            torch.Tensor[size of batch, 1]: The possibilities that model judging the corresponding input signals is real. 
        '''        
        x = x.unsqueeze(1)
        x = self.conv1(x)
        x = self.batchNorm1(x)
        x = self.depthwiseconv2(x)
        x = self.batchNorm2(x)
        x = F.elu(x)
        x = self.pooling1(x)
        x = self.separa1conv3(x)
        x = self.separa2conv4(x)
        x = self.batchNorm3(x)
        x = F.elu(x)
        x = self.pooling2(x)
        x = x.reshape((x.shape[0],-1))         
        x = self.fc1(x)
        x=torch.sigmoid(x)
        return x

