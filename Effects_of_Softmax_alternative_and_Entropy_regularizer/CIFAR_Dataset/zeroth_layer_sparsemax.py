# -*- coding: utf-8 -*-
"""zeroth-layer-spherical-softmax-ipynb.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1dURSM6VLPJxwYq2t4BSu0k5dsf-btK-c
"""

!pwd

path = '../run_' # change to save directory

#!pip install sparsemax  # uncomment if sparsemax is not installed

import torch.nn as nn
import torch.nn.functional as F
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import torch
import torchvision
import torchvision.transforms as transforms
from torch.utils.data import Dataset, DataLoader
from torchvision import transforms, utils
from matplotlib import pyplot as plt
import copy
#from sparsemax import Sparsemax
import torch.optim as optim



# Ignore warnings
import warnings
warnings.filterwarnings("ignore")
#n_seed = 0
#k = 0

torch.backends.cudnn.deterministic = True
torch.backends.cudnn.benchmark= False

transform = transforms.Compose(
    [transforms.ToTensor(),
     transforms.Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5))])

trainset = torchvision.datasets.CIFAR10(root='./data', train=True, download=True, transform=transform)


testset = torchvision.datasets.CIFAR10(root='./data', train=False, download=True, transform=transform)

trainloader = torch.utils.data.DataLoader(trainset, batch_size=10, shuffle=False)
testloader = torch.utils.data.DataLoader(testset, batch_size=10, shuffle=False)


classes = ('plane', 'car', 'bird', 'cat', 'deer', 'dog', 'frog', 'horse', 'ship', 'truck')

foreground_classes = {'plane', 'car', 'bird'}
#foreground_classes = {'bird', 'cat', 'deer'}
background_classes = {'cat', 'deer', 'dog', 'frog', 'horse', 'ship', 'truck'}
#background_classes = {'plane', 'car', 'dog', 'frog', 'horse','ship', 'truck'}

fg1,fg2,fg3 = 0,1,2

dataiter = iter(trainloader)
background_data=[]
background_label=[]
foreground_data=[]
foreground_label=[]
batch_size=10

for i in range(5000):
  images, labels = dataiter.next()
  for j in range(batch_size):
    if(classes[labels[j]] in background_classes):
      img = images[j].tolist()
      background_data.append(img)
      background_label.append(labels[j])
    else:
      img = images[j].tolist()
      foreground_data.append(img)
      foreground_label.append(labels[j])
            
foreground_data = torch.tensor(foreground_data)
foreground_label = torch.tensor(foreground_label)
background_data = torch.tensor(background_data)
background_label = torch.tensor(background_label)

def create_mosaic_img(bg_idx,fg_idx,fg): 
  """
  bg_idx : list of indexes of background_data[] to be used as background images in mosaic
  fg_idx : index of image to be used as foreground image from foreground data
  fg : at what position/index foreground image has to be stored out of 0-8
  """
  image_list=[]
  j=0
  for i in range(9):
    if i != fg:
      image_list.append(background_data[bg_idx[j]])#.type("torch.DoubleTensor"))
      j+=1
    else: 
      image_list.append(foreground_data[fg_idx])#.type("torch.DoubleTensor"))
      label = foreground_label[fg_idx]- fg1  # minus fg1 because our fore ground classes are fg1,fg2,fg3 but we have to store it as 0,1,2
  #image_list = np.concatenate(image_list ,axis=0)
  image_list = torch.stack(image_list) 
  return image_list,label

desired_num = 30000
mosaic_list_of_images =[]      # list of mosaic images, each mosaic image is saved as list of 9 images
fore_idx =[]                   # list of indexes at which foreground image is present in a mosaic image i.e from 0 to 9               
mosaic_label=[]                # label of mosaic image = foreground class present in that mosaic
for i in range(desired_num):
  np.random.seed(i)
  bg_idx = np.random.randint(0,35000,8)
  fg_idx = np.random.randint(0,15000)
  fg = np.random.randint(0,9)
  fore_idx.append(fg)
  image_list,label = create_mosaic_img(bg_idx,fg_idx,fg)
  mosaic_list_of_images.append(image_list)
  mosaic_label.append(label)

class MosaicDataset(Dataset):
  """MosaicDataset dataset."""

  def __init__(self, mosaic_list_of_images, mosaic_label, fore_idx):
    """
      Args:
        csv_file (string): Path to the csv file with annotations.
        root_dir (string): Directory with all the images.
        transform (callable, optional): Optional transform to be applied
            on a sample.
    """
    self.mosaic = mosaic_list_of_images
    self.label = mosaic_label
    self.fore_idx = fore_idx

  def __len__(self):
    return len(self.label)

  def __getitem__(self, idx):
    return self.mosaic[idx] , self.label[idx], self.fore_idx[idx]

batch = 250
msd = MosaicDataset(mosaic_list_of_images, mosaic_label , fore_idx)
train_loader = DataLoader( msd,batch_size= batch ,shuffle=True)

"""# Models"""

class Focus(nn.Module):
  def __init__(self):
    super(Focus, self).__init__()
    self.conv1 = nn.Conv2d(in_channels=3, out_channels=32, kernel_size=3, padding=0,bias=False)
    self.conv2 = nn.Conv2d(in_channels=32, out_channels=64, kernel_size=3, padding=0,bias=False)
    self.conv3 = nn.Conv2d(in_channels=64, out_channels=64, kernel_size=3, padding=0,bias=False)
    self.conv4 = nn.Conv2d(in_channels=64, out_channels=128, kernel_size=3, padding=0,bias=False)
    self.conv5 = nn.Conv2d(in_channels=128, out_channels=256, kernel_size=3, padding=0,bias=False)
    self.conv6 = nn.Conv2d(in_channels=256, out_channels=256, kernel_size=3, padding=1,bias=False)
    self.pool = nn.MaxPool2d(kernel_size=2, stride=2)
    self.batch_norm1 = nn.BatchNorm2d(32,track_running_stats=False)
    self.batch_norm2 = nn.BatchNorm2d(64,track_running_stats=False)
    self.batch_norm3 = nn.BatchNorm2d(256,track_running_stats=False)
    self.dropout1 = nn.Dropout2d(p=0.05)
    self.dropout2 = nn.Dropout2d(p=0.1)
    self.fc1 = nn.Linear(256,64,bias=False)
    self.fc2 = nn.Linear(64, 32,bias=False)
    self.fc3 = nn.Linear(32, 10,bias=False)
    self.fc4 = nn.Linear(10, 1,bias=False)
    
    torch.nn.init.xavier_normal_(self.conv1.weight)
    torch.nn.init.xavier_normal_(self.conv2.weight)
    torch.nn.init.xavier_normal_(self.conv3.weight)
    torch.nn.init.xavier_normal_(self.conv4.weight)
    torch.nn.init.xavier_normal_(self.conv5.weight)
    torch.nn.init.xavier_normal_(self.conv6.weight)

    torch.nn.init.xavier_normal_(self.fc1.weight)
    torch.nn.init.xavier_normal_(self.fc2.weight)
    torch.nn.init.xavier_normal_(self.fc3.weight)
    torch.nn.init.xavier_normal_(self.fc4.weight)
    
    self.sparsemax = Sparsemax(dim=-1) 


  def forward(self,z):  #y is avg image #z batch of list of 9 images
    y = torch.zeros([batch,3, 32,32], dtype=torch.float64)
    x = torch.zeros([batch,9],dtype=torch.float64)
    #ftr = torch.zeros([batch,9,3,32,32])
    y = y.to("cuda")
    x = x.to("cuda")
    #ftr = ftr.to("cuda")
    
    for i in range(9):
        out = self.helper(z[:,i])
        #print(out.shape)
        x[:,i] = out[:,0]
     
    
    x =self.sparsemax(x)

    for i in range(9):            
      x1 = x[:,i]          
      y = y + torch.mul(x1[:,None,None,None],z[:,i])

    return x, y #alpha,avg_data
    
  def helper(self, x):

    x = self.conv1(x)
    x = F.relu(self.batch_norm1(x))

    x = (F.relu(self.conv2(x)))
    x = self.pool(x)
    
    x = self.conv3(x)
    x = F.relu(self.batch_norm2(x))

    x = (F.relu(self.conv4(x)))
    x = self.pool(x)
    x = self.dropout1(x)

    x = self.conv5(x)
    
    x = F.relu(self.batch_norm3(x))

    x = self.conv6(x)
    
    x = F.relu(x)
    x = self.pool(x)

    x = x.view(x.size(0), -1)

    x = self.dropout2(x)
    x = F.relu(self.fc1(x))
    x = F.relu(self.fc2(x))
    x = self.dropout2(x)
    x = F.relu(self.fc3(x))
    x = self.fc4(x)
    return x

class Classification(nn.Module):
  def __init__(self):
    super(Classification, self).__init__()
    self.conv1 = nn.Conv2d(in_channels=3, out_channels=128, kernel_size=3, padding=1)
    self.conv2 = nn.Conv2d(in_channels=128, out_channels=128, kernel_size=3, padding=1)
    self.conv3 = nn.Conv2d(in_channels=128, out_channels=256, kernel_size=3, padding=1)
    self.conv4 = nn.Conv2d(in_channels=256, out_channels=256, kernel_size=3, padding=1)
    self.conv5 = nn.Conv2d(in_channels=256, out_channels=512, kernel_size=3, padding=1)
    self.conv6 = nn.Conv2d(in_channels=512, out_channels=512, kernel_size=3, padding=1)
    self.pool = nn.MaxPool2d(kernel_size=2, stride=2,padding=1)
    self.batch_norm1 = nn.BatchNorm2d(128,track_running_stats=False)
    self.batch_norm2 = nn.BatchNorm2d(256,track_running_stats=False)
    self.batch_norm3 = nn.BatchNorm2d(512,track_running_stats=False)
    self.dropout1 = nn.Dropout2d(p=0.05)
    self.dropout2 = nn.Dropout2d(p=0.1)
    self.global_average_pooling = nn.AvgPool2d(kernel_size=4)
    self.fc1 = nn.Linear(512,128)
    # self.fc2 = nn.Linear(128, 64)
    # self.fc3 = nn.Linear(64, 10)
    self.fc2 = nn.Linear(128, 3)


    torch.nn.init.xavier_normal_(self.conv1.weight)
    torch.nn.init.xavier_normal_(self.conv2.weight)
    torch.nn.init.xavier_normal_(self.conv3.weight)
    torch.nn.init.xavier_normal_(self.conv4.weight)
    torch.nn.init.xavier_normal_(self.conv5.weight)
    torch.nn.init.xavier_normal_(self.conv6.weight)

    torch.nn.init.zeros_(self.conv1.bias)
    torch.nn.init.zeros_(self.conv2.bias)
    torch.nn.init.zeros_(self.conv3.bias)
    torch.nn.init.zeros_(self.conv4.bias)
    torch.nn.init.zeros_(self.conv5.bias)
    torch.nn.init.zeros_(self.conv6.bias)


    torch.nn.init.xavier_normal_(self.fc1.weight)
    torch.nn.init.xavier_normal_(self.fc2.weight)
    torch.nn.init.zeros_(self.fc1.bias)
    torch.nn.init.zeros_(self.fc2.bias)


  def forward(self, x):
    x = self.conv1(x)
    x = F.relu(self.batch_norm1(x))

    x = (F.relu(self.conv2(x)))
    x = self.pool(x)
    
    x = self.conv3(x)
    x = F.relu(self.batch_norm2(x))

    x = (F.relu(self.conv4(x)))
    x = self.pool(x)
    x = self.dropout1(x)

    x = self.conv5(x)
    x = F.relu(self.batch_norm3(x))

    x = (F.relu(self.conv6(x)))
    x = self.pool(x)

    x = self.global_average_pooling(x)
    x = x.squeeze()

    x = self.dropout2(x)
    x = F.relu(self.fc1(x))

    x = self.fc2(x)
    return x

test_images =[]        #list of mosaic images, each mosaic image is saved as laist of 9 images
fore_idx_test =[]                   #list of indexes at which foreground image is present in a mosaic image                
test_label=[]                # label of mosaic image = foreground class present in that mosaic
for i in range(10000):
  np.random.seed(i+30000)
  bg_idx = np.random.randint(0,35000,8)
  fg_idx = np.random.randint(0,15000)
  fg = np.random.randint(0,9)
  fore_idx_test.append(fg)
  image_list,label = create_mosaic_img(bg_idx,fg_idx,fg)
  test_images.append(image_list)
  test_label.append(label)

test_data = MosaicDataset(test_images,test_label,fore_idx_test)
test_loader = DataLoader( test_data,batch_size= batch ,shuffle=False)

def calculate_attn_loss(dataloader,what,where,criter):
    what.eval()
    where.eval()
    r_loss = 0
    alphas = []
    lbls = []
    pred = []
    fidices = []
    with torch.no_grad():
        for i, data in enumerate(dataloader, 0):
            inputs, labels,fidx = data
            lbls.append(labels)
            fidices.append(fidx)
            inputs = inputs.double()
            inputs, labels = inputs.to("cuda"),labels.to("cuda")



            alpha,avg = where(inputs)
            outputs = what(avg)
      
      
            _, predicted = torch.max(outputs.data, 1)
            pred.append(predicted.cpu().numpy())
            alphas.append(alpha.cpu().numpy())

            loss = criter(outputs,labels)
            r_loss += loss.item()


    alphas = np.concatenate(alphas,axis=0)
    pred = np.concatenate(pred,axis=0)
    lbls = np.concatenate(lbls,axis=0)
    fidices = np.concatenate(fidices,axis=0)
    #print(alphas.shape,pred.shape,lbls.shape,fidices.shape) 
    
    # value>0.01  here sum over all data points is returned to take average divide by number of data points
    sparsity_val = np.sum(np.sum(alphas>0.01,axis=1))
    
    
    # simplex distance  here sum over all data points is returned to take average divide by number of data points
    argmax_index = np.argmax(alphas,axis=1)
    simplex_pt = np.zeros(alphas.shape)
    simplex_pt[np.arange(argmax_index.size),argmax_index] = 1
    
    shortest_distance_simplex = np.sum(np.sqrt(np.sum((alphas-simplex_pt)**2,axis=1))) 
    
    # entropy  here sum over all data points is returned to take average divide by number of data points
    entropy = np.sum(np.nansum(-alphas*np.log2(alphas),axis=1))
    
    
    
    
    
    
    
    analysis = analyse_data(alphas,lbls,pred,fidices)
    return analysis,[sparsity_val,shortest_distance_simplex,entropy]

def analyse_data(alphas,lbls,predicted,f_idx):
    '''
       analysis data is created here
    '''
    batch = len(predicted)
    amth,alth,ftpt,ffpt,ftpf,ffpf = 0,0,0,0,0,0
    for j in range (batch):
        focus = np.argmax(alphas[j])
        if(alphas[j][focus] >= 0.5):
            amth +=1
        else:
            alth +=1
        if(focus == f_idx[j] and predicted[j] == lbls[j]):
            ftpt += 1
        elif(focus != f_idx[j] and predicted[j] == lbls[j]):
            ffpt +=1
        elif(focus == f_idx[j] and predicted[j] != lbls[j]):
            ftpf +=1
        elif(focus != f_idx[j] and predicted[j] != lbls[j]):
            ffpf +=1

    return [ftpt,ffpt,ftpf,ffpf,amth,alth]

"""# training"""

n_seed =[0,1,2]
lr = [0.0005,0.001,0.003]

Analysis_ = {}
Train_Loss_ = []

for n_seed_ in n_seed:
    for lr_ in lr:
        analyse_data_train = []
        analyse_data_test = []
        sparsty_train = []
        sparsty_test = []
        
        tr_loss = []
        
        print("initializing models using seed",n_seed_)
        torch.manual_seed(n_seed_)
        focus_net = Focus().double()
        focus_net = focus_net.to("cuda")


        torch.manual_seed(n_seed_)
        classify = Classification().double()
        classify = classify.to("cuda")


        criterion = nn.CrossEntropyLoss()


        print("using lr",lr_)

        optimizer_focus = optim.Adam(focus_net.parameters(), lr=lr_)#, momentum=0.9)
        optimizer_classify = optim.Adam(classify.parameters(), lr=lr_)#, momentum=0.9)
        
        analysis_data_train, sparsity_value_train =calculate_attn_loss(train_loader,classify,focus_net,criterion)
        
        analysis_data_test, sparsity_value_test =calculate_attn_loss(test_loader,classify,focus_net,criterion)
        
        analyse_data_train.append(analysis_data_train)
        analyse_data_test.append(analysis_data_test)
        sparsty_train.append(sparsity_value_train)
        sparsty_test.append(sparsity_value_test)
        
        nos_epochs = 50
        
        
        focus_net.train()
        classify.train()
        
        for epoch in range(nos_epochs):  # loop over the dataset multiple time
            focus_net.train()
            classify.train()
            
            epoch_loss = []
            cnt=0
            running_loss = 0
            
            iteration = desired_num // batch
            for i, data in  enumerate(train_loader):
                inputs , labels , fore_idx = data
                inputs = inputs.double()
                inputs, labels = inputs.to("cuda"), labels.to("cuda")
                
                # zero the parameter gradients
                optimizer_focus.zero_grad()
                optimizer_classify.zero_grad()
            
                alphas, avg_images = focus_net(inputs)
                outputs = classify(avg_images)

                # outputs, alphas, avg_images = classify(inputs)

                _, predicted = torch.max(outputs.data, 1)
                
                loss = criterion(outputs, labels)
                loss.backward()
                optimizer_focus.step()
                optimizer_classify.step()

                running_loss += loss.item()
                mini = 60
                if cnt % mini == mini-1:    # print every 60 mini-batches
                    print('[%d, %5d] loss: %.3f' %(epoch + 1, cnt + 1, running_loss / mini))
                    epoch_loss.append(running_loss/mini)
                    running_loss = 0.0
                cnt=cnt+1
                
            tr_loss.append(np.mean(epoch_loss))
                
            if epoch % 1 == 0:
                analysis_data_train, sparsity_value_train = calculate_attn_loss(train_loader,classify,focus_net,criterion)
        
                analysis_data_test, sparsity_value_test = calculate_attn_loss(test_loader,classify,focus_net,criterion)    
                
                analyse_data_train.append(analysis_data_train)
                analyse_data_test.append(analysis_data_test)
                sparsty_train.append(sparsity_value_train)
                sparsty_test.append(sparsity_value_test)
            if(np.mean(epoch_loss) <= 0.05):
                break
        print('Finished Training') 
        print("train FTPT Analysis and sparsity values",analysis_data_train,sparsity_value_train)
        print("test FTPT Analysis and sparsity values",analysis_data_test,sparsity_value_test)
        
        torch.save(focus_net.state_dict(),path+"seed_"+str(n_seed_)+"lr_"+str(lr_)+"weights_focus.pt")  
        torch.save(classify.state_dict(),path+"seed_"+str(n_seed_)+"lr_"+str(lr_)+"weights_classify.pt")
         
        Analysis_["train_seed_"+str(n_seed_)+"_lr_"+str(lr_)] = np.array(analyse_data_train)
        Analysis_["test_seed_"+str(n_seed_)+"_lr_"+str(lr_)]  = np.array(analyse_data_test)
        Analysis_["train_sparsity_"+str(n_seed_)+"_lr_"+str(lr_)] = np.array(sparsty_train)
        Analysis_["test_sparsity_"+str(n_seed_)+"_lr_"+str(lr_)] = np.array(sparsty_test)
        
        Train_Loss_.append(tr_loss)

np.save("analysis.npy",Analysis_)
np.save("training_loss.npy",Train_Loss_)

Analysis_

for i in range(len(Train_Loss_)):
    plt.figure(figsize=(6,5))
    plt.plot(np.arange(1,len(Train_Loss_[i])+1),Train_Loss_[i])
    plt.xlabel("epochs", fontsize=14, fontweight = 'bold')
    plt.ylabel("Loss", fontsize=14, fontweight = 'bold')
    plt.xticks(np.arange(1,epoch+2))
    plt.title("Train Loss")
    # #plt.grid()
    plt.show()

for seed_ in n_seed:
    for lr_ in lr:
        data = Analysis_['train_seed_'+ str(seed_)+"_lr_" +str(lr_)]
        plt.figure(figsize=(6,5))
        plt.plot(np.arange(0,len(data)),data[:,0]/300, label ="FTPT ")
        plt.plot(np.arange(0,len(data)),data[:,1]/300, label ="FFPT ")
        plt.plot(np.arange(0,len(data)),data[:,2]/300, label ="FTPF ")
        plt.plot(np.arange(0,len(data)),data[:,3]/300, label ="FFPF ")
        plt.title("On Training set " + 'seed ' + str(seed_)+" lr " +str(lr_))
        #plt.legend(loc='center left', bbox_to_anchor=(1, 0.5))
        plt.xlabel("epochs", fontsize=14, fontweight = 'bold')
        plt.ylabel("percentage train data", fontsize=14, fontweight = 'bold')
        # plt.xlabel("epochs")
        # plt.ylabel("training data")
        plt.legend()

        plt.savefig(path + 'seed ' + str(seed_)+" lr " +str(lr_)+ "_train.png",bbox_inches="tight")
        plt.savefig(path + 'seed ' + str(seed_)+" lr " +str(lr_)+ "_train.pdf",bbox_inches="tight")
        plt.grid()
        plt.show()

for seed_ in n_seed:
    for lr_ in lr:
        data = Analysis_['test_seed_'+ str(seed_)+"_lr_" +str(lr_)]
        plt.figure(figsize=(6,5))
        plt.plot(np.arange(0,len(data)),data[:,0]/100, label ="FTPT ")
        plt.plot(np.arange(0,len(data)),data[:,1]/100, label ="FFPT ")
        plt.plot(np.arange(0,len(data)),data[:,2]/100, label ="FTPF ")
        plt.plot(np.arange(0,len(data)),data[:,3]/100, label ="FFPF ")
        plt.title("On Testing set " + 'seed ' + str(seed_)+" lr " +str(lr_))
        #plt.legend(loc='center left', bbox_to_anchor=(1, 0.5))
        plt.xlabel("epochs", fontsize=14, fontweight = 'bold')
        plt.ylabel("percentage test data", fontsize=14, fontweight = 'bold')
        # plt.xlabel("epochs")
        # plt.ylabel("training data")
        plt.legend()

        plt.savefig(path + 'seed ' + str(seed_)+" lr " +str(lr_)+"_test.png",bbox_inches="tight")
        plt.savefig(path + 'seed ' + str(seed_)+" lr " +str(lr_)+ "_test.pdf",bbox_inches="tight")
        plt.grid()
        plt.show()
