# Copyright 2021 BlobCity, Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


import os
import optuna
import warnings
from blobcity.main import modelSelection
from sklearn.exceptions import ConvergenceWarning
from sklearn.model_selection import train_test_split,cross_val_score
from sklearn.metrics import r2_score,mean_squared_error,mean_absolute_error,f1_score,precision_score,recall_score
with warnings.catch_warnings():
    warnings.filterwarnings("ignore", category=ConvergenceWarning)
    warnings.filterwarnings("ignore", category=DeprecationWarning)
    os.environ["PYTHONWARNINGS"] = "ignore"
optuna.logging.set_verbosity(optuna.logging.WARNING)
"""
Python files consist of function to perform parameter tuning using optuna framework
"""

#Early stopping class
class EarlyStopper():
    iter_stop = 10
    iter_count = 0
    best_score = None

def early_stopping_opt(study, trial):
    """
    param1:optuna.study.Study 
    param2:optuna trial
    
    The function decides whether to stop parameter tunning based on the accuracy of the current trial. 
    Condition to stop trials: if accuracy is more than equal to 99%. 
    The second condition is to check whether accuracy is between 90%-99% and 
    whether the current best accuracy has not changed for the last ten trials.

    """
    if EarlyStopper.best_score == None: EarlyStopper.best_score = study.best_value
    if study.best_value >= 0.99 : study.stop()
    if study.best_value > EarlyStopper.best_score:
        EarlyStopper.best_score = study.best_value
        EarlyStopper.iter_count = 0
    else:
        if  study.best_value > 0.90 and study.best_value < 0.99:
            if EarlyStopper.iter_count < EarlyStopper.iter_stop:
                EarlyStopper.iter_count=EarlyStopper.iter_count+1  
            else:
                EarlyStopper.iter_count = 0
                EarlyStopper.best_score = None
                study.stop()
    return

def regression_metrics(y_true,y_pred):
    """
    param1: pandas.Series/pandas.DataFrame/numpy.darray
    param2: pandas.Series/pandas.DataFrame/numpy.darray 

    return: dictionary

    Function accept actual prediction labels from the dataset and predicted values from the model and utilizes this
    two values/data to calculate r2 score, mean absolute error, mean squared error, and root mean squared error at same time add them to result dictionary.
    Finally return the result dictionary 
    
    """
    result=dict()
    result['R2']=r2_score(y_true, y_pred)
    result['MAE']=mean_absolute_error(y_true, y_pred)
    result['MSE']=mean_squared_error(y_true, y_pred)
    result['RMSE']=mean_squared_error(y_true, y_pred,squared=False)
    return result

def classification_metrics(y_true,y_pred):
    """
    param1: pandas.Series/pandas.DataFrame/numpy.darray
    param2: pandas.Series/pandas.DataFrame/numpy.darray 

    return: dictionary

    Function accept actual prediction labels from the dataset and predicted values from the model and utilizes this
    two values/data to calculate f1 score,precision score, and recall for the classification problem. And finally 
    return them in a dictionary
    """
    result=dict()
    result['F1-Score']=f1_score(y_true, y_pred, average="weighted")
    result['precision']=precision_score(y_true, y_pred,average="weighted")
    result['recall']=recall_score(y_true, y_pred,average="weighted")
    return result

def metricResults(model,X,Y,ptype):
    """
    param1: model object (keras/sklearn/xgboost/catboost/lightgbm)
    param2: pandas.DataFrame
    param3: pandas.DataFrame/pandas.Series/numpy.darray
    param4: String

    return: Dictionary

    Function first perform an train test split of 80:20 split and train the selected model (with parameter tuning) 
    on training set. based on problem type call appropriate metric function either regression_metrics() or classification_metrics()
    return the resulting output(Dictionary).
    """
    X_train,X_test,y_train,y_test=train_test_split(X,Y,test_size=0.2,random_state=123)
    model=model.fit(X_train,y_train)
    y_pred=model.predict(X_test)
    results = classification_metrics(y_test,y_pred) if ptype =="Classification" else regression_metrics(y_test,y_pred)
    return results

def getParamList(modelkey,modelList):
    """
    param1: dictionary
    param2: dictionary
    function initialize global variables required for parameter tuning and modelclass object.
    """
    global modelName
    global parameter
    Best1=list(modelkey.keys())[0]
    modelName,parameter=modelList[Best1][0],modelList[Best1][1]

def getParams(trial):
    """
    param1: optuna.trial
    return: dictionary

    Function fetch different parameter values associated to model using appropriate optuna.trial class.
    then finally return the dictionary of parameters.
    """
    params=dict()
    for key,value in parameter.items():
        for datatype,arg in value.items():
            if datatype == "int":
                params[key]=trial.suggest_int(key,arg[0],arg[1])
            elif datatype=="float":
                params[key]=trial.suggest_float(key,arg[0],arg[1])
            elif datatype in ['str','bool','object']:
                params[key]=trial.suggest_categorical(key,arg)
    return params

def objective(trial):
    """
    param1: optuna.Trial
    return: float

    function trains model of randomized tuning parameter and return cross_validation score on specified kfold counts.
    the accuracy is average over the specified kfold counts.
    """
    params=getParams(trial)
    model=modelName(**params)
    score = cross_val_score(model, X, Y, n_jobs=-1, cv=cv)
    accuracy = score.mean()
    return accuracy    

def tuneModel(dataframe,target,modelkey,modelList,ptype):
    """
    param1: pandas.DataFrame
    param2: string 
    param3: dictionary
    param4: dictionary
    return: tuple(model,parameter)

    Function first fetchs required parameter details for the specific model by calling getParamList function and number of required kfold counts.
    then start a optuna study operation to fetch best tuning parameter for the model.
    then initialize the model with parameter and trains it on dataset.csv
    finally returns a tuple with consist of trained model and parameters.
    """
    global X
    global Y
    global cv
    X,Y=dataframe.drop(target,axis=1),dataframe[target]
    cv=modelSelection.getKFold(X)
    getParamList(modelkey,modelList)
    try:
        study = optuna.create_study(direction="maximize")
        study.optimize(objective,n_trials=50,n_jobs=-1,callbacks=[early_stopping_opt])
        metric_result=metricResults(modelName(**study.best_params),X,Y,ptype)
        model = modelName(**study.best_params).fit(X,Y)
        return (model,study.best_params,study.best_value,metric_result)
    except Exception as e:
        print(e)