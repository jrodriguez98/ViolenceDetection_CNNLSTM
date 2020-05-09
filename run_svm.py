import os
from sklearn.svm import OneClassSVM
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split
import glob
from DatasetBuilder import frame_loader, pad_sequences, get_sequences, createDataset
from random import shuffle

from keras.models import load_model, Model
import numpy as np
import pandas as pd

def get_positive_class_path(dataset_name, dataset_frame_path):
    """Return a train/test split of the paths

    Parameters:
    datasets_frame_path (dict): key: name of the dataset, value: root directory of frames

    Returns:
    train_path, test_path


    """
    video_frames_path_no = []
    video_frames_path_fight = []
    
    
    for entry in os.scandir(dataset_frame_path):
        if entry.is_dir():
            complete_path = os.path.join(dataset_frame_path, entry.name)

            if dataset_name == "hocky":
                if entry.name.startswith('fi'):
                    video_frames_path_fight.append(complete_path)
                else:
                    video_frames_path_no.append(complete_path)

            elif dataset_name == "violentflow":
                if "violence" in entry.name:
                    video_frames_path_fight.append(complete_path)
                else:
                    video_frames_path_no.append(complete_path)
            
            elif dataset_name == "movies":
                if "fi" in entry.name:
                    video_frames_path_fight.append(complete_path)
                else:
                    video_frames_path_no.append(complete_path)
                
    
    train_path, test_path =  train_test_split(video_frames_path_no, test_size=0.20, random_state=42)
    
    shuffle(video_frames_path_fight) # Disorganize the figths list
    test_path.extend(video_frames_path_fight[:len(test_path)]) # 1/2 no fights and 1/2 fights

    len_test = len(test_path)
    labels_test = [1 if i < len_test/2 else -1 for i in range(len_test)]

    return train_path, test_path, labels_test


def get_sequences_x(data_paths, figure_shape, seq_length,classes=1, use_augmentation = False, use_crop=True, crop_x_y=None):
    X = []
    seq_len = 0
    for data_path in data_paths:
        frames = sorted(glob.glob(os.path.join(data_path, '*jpg')))
        x = frame_loader(frames, figure_shape)
        if(crop_x_y):
            x = [crop_img__remove_Dark(x_,crop_x_y[0],crop_x_y[1],x_.shape[0],x_.shape[1],figure_shape) for x_ in x]
        if use_augmentation:
            rand = scipy.random.random()
            corner=""
            if rand > 0.5:
                if(use_crop):
                    corner=random.choice(corner_keys)
                    x = [crop_img(x_,figure_shape,0.7,corner) for x_ in x]
                x = [frame.transpose(1, 0, 2) for frame in x]
                if(Debug_Print_AUG):
                    to_write = [list(a) for a in zip(frames, x)]
                    [cv2.imwrite(x_[0] + "_" + corner, x_[1] * 255) for x_ in to_write]

        x = [x[i] - x[i+1] for i in range(len(x)-1)]
        X.append(x)
        
    X = pad_sequences(X, maxlen=seq_length, padding='pre', truncating='pre')
    if classes > 1:
        x_ = to_categorical(x_,classes)
    return np.array(X)


def data_generator_svm(data_paths,batch_size,figure_shape,seq_length,use_aug,use_crop,crop_x_y,classes=1, random=True):
    while True:
        indexes = np.arange(len(data_paths))
        if random:
            np.random.shuffle(indexes)

        select_indexes = indexes[:batch_size]
        data_paths_batch = [data_paths[i] for i in select_indexes]

        X = get_sequences_x(data_paths_batch, figure_shape, seq_length, crop_x_y=crop_x_y, classes=classes)

        yield X

def get_generators_svm(dataset_name, dataset_frames_path, fix_len, figure_size, force, classes=1, use_aug=False,
                   use_crop=True, crop_dark=None):

    train_path, test_path, test_y = get_positive_class_path(dataset_name, dataset_frames_path)

    if fix_len is not None:
        avg_length = fix_len
    crop_x_y = None
    if (crop_dark):
        crop_x_y = crop_dark[dataset_name]

    len_train, len_test = len(train_path), len(test_path)
    
    train_x = data_generator_svm(train_path, batch_size, figure_size, avg_length, use_aug, use_crop, crop_x_y, classes=1)

    test_x = data_generator_svm(test_path, batch_size, figure_size, avg_length, use_aug, use_crop, crop_x_y, classes=1, random=False)

    test_y = np.asarray(test_y)

    print('TRAIN LEN {}'.format(dataset_name))
    print(len_train)  
    print('TEST SHAPE {}'.format(dataset_name))
    print(len_test)     

    assert len_test == len(test_y)                                       

    return train_x, test_x, test_y, avg_length, len_train, len_test


def get_model(dataset_model_path, num_output_features=10):

    if (num_output_features == 10):
        index = -4
    elif (num_output_features == 256):
        index = -7
    elif (num_output_features == 1000):
        index = -9
    else:
        raise Exception('num_output_features can not be {}, possible values [10, 256, 1000]'.format(num_output_features))

    model = load_model(dataset_model_path)

    input_layer = model.input
    output_layer = model.layers[index].output

    intermediate_model = Model(inputs=model.input, output=output_layer) # New model for deep representation

    # intermediate_model.summary()

    return intermediate_model


def compute_representation(dataset_name, datasets_paths, num_output_features):

    train_x, test_x, test_y, avg_length, len_train, len_test = get_generators_svm(dataset_name, datasets_paths[dataset_name]['frames'], fix_len, figure_size, force, classes=1, use_aug=False,
                   use_crop=True, crop_dark=None)

    model = get_model(datasets_paths[dataset_name]['model'], num_output_features=num_output_features)

    train_x = model.predict_generator(train_x, steps=int(len_train/batch_size))
    test_x = model.predict_generator(test_x, steps=int(len_test/batch_size))
    # Save representations in csv
    #np.savetxt(datasets_paths[dataset_name]['svm_features'], svm_inputs, delimiter=',')

    return train_x, test_x, test_y

def join_datasets (train_x_hocky, train_x_violentflow, train_x_movies, test_x_hocky, test_x_violentflow, test_x_movies, test_y_hocky, test_y_violent_flow, test_y_movies):
    
    join_train_x = np.concatenate((train_x_hocky, train_x_violentflow, train_x_movies), axis=0)

    join_test_x = np.concatenate((test_x_hocky, test_x_violentflow, test_x_movies), axis=0)

    join_test_y = np.concatenate((test_y_hocky, test_y_violent_flow, test_y_movies), axis=0)

    return join_train_x, join_test_x, join_test_y

def train_eval_svm(train_x, test_x, test_y):
    
    clf = OneClassSVM(kernel='poly', gamma='scale')
    y_train_pred = clf.fit_predict(train_x)

    num_errors = len([x for x in y_train_pred if x != 1])
    acc_train = num_errors/len(y_train_pred)

    y_pred = clf.predict(test_x) # Predictions
    acc_test = accuracy_score(test_y, y_pred) # Compute accuracy
    print(y_pred)
    result = {}
    result['accuracy'] = acc_test

    return result



def compute_all(num_output_features):
    results = []

    datasets_paths = dict(
        hocky=dict(frames='data/raw_frames/hocky', model="models/hocky.h5", svm_features="svm_features/hocky_{}.csv".format(num_output_features)),
        violentflow=dict(frames='data/raw_frames/violentflow', model="models/violentflow.h5", svm_features="svm_features/violentflow_{}.csv".format(num_output_features)),
        movies=dict(frames='data/raw_frames/movies', model="models/movies.h5", svm_features="svm_features/movies_{}.csv".format(num_output_features))
    )
    # Compute the inner represention on the 3 datasets independently
    train_x_hocky, test_x_hocky, test_y_hocky = compute_representation('hocky', datasets_paths, num_output_features)
    result = train_eval_svm(train_x_hocky, test_x_hocky, test_y_hocky)
    result ['dataset'] = 'hocky'
    results.append(result)

    train_x_violentflow, test_x_violentflow, test_y_violent_flow = compute_representation('violentflow', datasets_paths, num_output_features)
    result = train_eval_svm(train_x_violentflow, test_x_violentflow, test_y_violent_flow)
    result ['dataset'] = 'violentflow'
    results.append(result)

    train_x_movies, test_x_movies, test_y_movies  = compute_representation('movies', datasets_paths, num_output_features)
    result = train_eval_svm(train_x_movies, test_x_movies, test_y_movies)
    result ['dataset'] = 'movies'
    results.append(result)

    join_train_x, join_test_x, join_test_y = join_datasets(train_x_hocky, train_x_violentflow, train_x_movies, test_x_hocky, test_x_violentflow, test_x_movies, test_y_hocky, test_y_violent_flow, test_y_movies)

    result = train_eval_svm(join_train_x, join_test_x, join_test_y)
    result ['dataset'] = 'join'
    results.append(result)

    pd.DataFrame(results).to_csv("results/results_svm_{}.csv".format(num_output_features))

    #np.savetxt("svm_features/join_train_x_{}.csv".format(num_output_features), join_train_x, delimiter=',')


def create_dirs():
    if not os.path.exists('data/raw_frames'):
        os.makedirs('data/raw_frames')

    if not os.path.exists('models'):
        os.makedirs('models')

    if not os.path.exists('svm_features'):
        os.makedirs('svm_features')

    
# Prueba
fix_len = 20
figure_size = 244
force = True
batch_size = 2

#diccionario = dict(hocky='data/raw_frames/hocky')

create_dirs()

compute_all(10)
compute_all(256)
compute_all(1000)
