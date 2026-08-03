## Require KERAS classes
```
from keras.models import Sequential
from keras.layers import Dense, Activation
```
## Create variable "model"
```
model = Sequential(layers)
```
## To the constructor, we pass an array of Dense objects.
Each of these objects called Dense are actually layers.
```
Layers =[
Dense(units = 3, input_shape=(2,), activation='relu')
Dense(units = 2, activation='softmax')
]
```
==Dense is the most basic kind of layer in an ANN== and that each output of a dense layer is computed using every input to the layer. 

--> More on layers [[Why have different types of layers]]
- We can see that each nodes are all connected to every nodes of the next layers. This is how we know that the output layer in the image is a dense layer.

> The first parameter passed to the ==Dense tell us how many neurons== it should have

> The input shape parameter ==`input_shape=(2,)` tell us how many neurons our Input Layer has== ( in this case we have 2)

> Activation Function are
> 1. activation='relu'
> 2. activation='softmax' 
> ==Activation Function are non-linear function that typically follows a dense layer==

## Defining The Neural Network In Code With Keras

![[ANN example.png]]

Given this, we have:
```
layers = [
Dense(units=6, input_shape=(8,), activation='relu'),
Dense(units=6, activation'relu'),
Dense(units=4, activation='softmax')
]
```

- Notice how the first Dense object specified in the list is not the input layer. ==The first Dense object is the first hidden layer.== The input layer is specified as a parameter to the first Dense object's constructor. 

- ==Our input shape is 8. Our first hidden layer has six nodes as does our second hidden layer, and our output layer has 4 nodes.== 

- We using activation='relu' for both hidden layers and activation='softmax' for our output layer. --> [[Activate Function In a Neural Network#What is An activate Function?]]

==Final look at the code:==
```
from keras.models import Sequential
from keras.layers import Dense, Activation

layers = [
    Dense(units=6, input_shape=(8,), activation='relu'),
    Dense(units=6, activation='relu'),
    Dense(units=4, activation='softmax')
]

model = Sequential(layers)
```

## Activation Functions In Code With Keras

Two ways to achieve 
We first import our classes
```
from keras.models import Sequential
from keras.layers import Dense, Activation
```

The first way is to specify an activation function is in the constructor of the layer like so

```
model = Sequential([
Dense(units=5, input_shape=(3,), activation='relu')
])
```

In this case, we have a Dense layer and we are specifying relu as our activation function activation='relu'

The second way is to add the layers and activation functions to our model after the model has been instantiated like so:

```
model = Sequential()
model.add(Dense(units=5, input_shape=(3,)))
model.add(Activation('relu'))
```

Remember that:
```
node output = activation(weighted sum of inputs)
```

For our example, this means that each output from the nodes in our Dense layer will be equal to the relu result of the weighted sums like

```
node output = relu(weighted sum of inputs)
```

## Training In Code With Keras

Begin with importing the required classes: 

```
import keras
from keras.models import Sequential
from keras.layers import Activation
from keras.layers.core import Dense
from keras.optimizers import Adam
from keras.metrics import categorical_crossentropy
```

Next, we define out model:
```
model = Sequential([
    Dense(units=16, input_shape=(1,), activation='relu'),
    Dense(units=32, activation='relu'),
    Dense(units=2, activation='sigmoid')
])
```

Before we can train, we must compile it:

```
model.compile(
    optimizer=Adam(learning_rate=0.0001), 
    loss='sparse_categorical_crossentropy', 
    metrics=['accuracy']
)
```

To the compile() function, we passing the optimizer, the loss function , and the metrics that we would like to see. 

Notice that the optimizer we have specified is called Adam. 'Adam' is just a variant of SGD. Inside the Adam constructor is where we specify the learning rate, and in this case we have chosen 0.0001. 

Finally, we fit out model to the data. Fitting the model to the data means to train the model on the data.

```
model.fit(
    x=scaled_train_samples, 
    y=train_labels, 
    batch_size=10, 
    epochs=20, 
    shuffle=True, 
    verbose=2
)
```

scaled_train_samples: is a numpy array consisting of the training samples.

train_labels: is a numpy array consisting of the corresponding labels for the training samples.

batch_size=10: specifies how many training samples should be sent to the model at once.

epochs=20 means that the complete training set (all of the samples) will be passed to the model a total of 20 times.

shuffle=True indicates that the data should first be shuffled before being passed to the model

verbose=2 indicates how much logging we will see as the model trains.

Expected output would look like: 

```
Epoch 1/20 0s - loss: 0.6400 - acc: 0.5576
Epoch 2/20 0s - loss: 0.6061 - acc: 0.6310
Epoch 3/20 0s - loss: 0.5748 - acc: 0.7010
Epoch 4/20 0s - loss: 0.5401 - acc: 0.7633
Epoch 5/20 0s - loss: 0.5050 - acc: 0.7990
Epoch 6/20 0s - loss: 0.4702 - acc: 0.8300
Epoch 7/20 0s - loss: 0.4366 - acc: 0.8495
Epoch 8/20 0s - loss: 0.4066 - acc: 0.8767
Epoch 9/20 0s - loss: 0.3808 - acc: 0.8814
Epoch 10/20 0s - loss: 0.3596 - acc: 0.8962
Epoch 11/20 0s - loss: 0.3420 - acc: 0.9043
Epoch 12/20 0s - loss: 0.3282 - acc: 0.9090
Epoch 13/20 0s - loss: 0.3170 - acc: 0.9129
Epoch 14/20 0s - loss: 0.3081 - acc: 0.9210
Epoch 15/20 0s - loss: 0.3014 - acc: 0.9190
Epoch 16/20 0s - loss: 0.2959 - acc: 0.9205
Epoch 17/20 0s - loss: 0.2916 - acc: 0.9238
Epoch 18/20 0s - loss: 0.2879 - acc: 0.9267
Epoch 19/20 0s - loss: 0.2848 - acc: 0.9252
Epoch 20/20 0s - loss: 0.2824 - acc: 0.9286
```

The output give is the epoch number, duration, Loss and accuracy. 

## Loss Functions In Code With Keras

We already have our model

```
model = Sequential([
    Dense(16, input_shape=(1,), activation='relu'),
    Dense(32, activation='relu'),
    Dense(2, activation='sigmoid')
])
```

we then compile it

```
model.compile(
    Adam(learning_rate=.0001), 
    loss='sparse_categorical_crossentropy', 
    metrics=['accuracy']
)
```
Looking at the second parameter of the call to compile(), we can see the specified loss function loss='sparse_categorical_crossentropy'.

The current available loss functions for Keras are as follows: 
- mean_squared_error
- mean_absolute_error
- mean_absolute_percentage_error
- mean_squared_logarithmic_error
- squared_hinge
- hinge
- categorical_hinge
- logcosh
- categorical_crossentropy
- sparse_categorical_crossentropy
- binary_crossentropy
- kullback_leibler_divergence
- poisson
- cosine_proximity

## Learning Rates in Keras
```
model = Sequential([
    Dense(units=16, input_shape=(1,), activation='relu'),
    Dense(units=32, activation='relu', kernel_regularizer=regularizers.l2(0.01)),
    Dense(units=2, activation='sigmoid')
])

model.compile(
    optimizer=Adam(learning_rate=0.0001), 
    loss='sparse_categorical_crossentropy', 
    metrics=['accuracy']
)
```

- With the line, where we are compiling our model, we can see that the first parameter we're specifying is our optimizer. In this case, we're using Adam as the optimizer for this model. 
- Now to our optimizer, we can optionally pass our learning rate by specifying the learning_rate parameter.
- The learning rate is optional, if not specify then kera will use default learning rate. 

Another way of specify the learning_rate:
```
model.optimizer.learning_rate = 0.01
```

## Using A Keras Model To Get A Prediction

```
predictions = model.predict(
x=scaled_test_samples,
batch_size = 10,
verbose = 0
)
```
The first item we have here is a variable we've called predictions. We're assuming that we already have our model built and trained. Our model in this example is the object called model. We're setting predictions equal to model.predict().

The predict() function is what we call to actually have the model make predictions. To the predict() function, we're passing the variable called scaled_test_samples. 