# Row155 Convolutional Networks

Exact description: "Extracts spatial features".
Source: https://docs.google.com/document/d/1kCtzves_4OGVKUdFUPC0bkvY3jQGnfpeeEJWe1mQ3xY/edit

Actual supplied-kernel single-channel 2D cross-correlation (kernel not flipped),
exact rational feature map, strides1..4, valid or same zero padding, identity or
ReLU activation. Same output dimensions ceil(image/stride); odd padding excess
on bottom/right. Existing planning method unchanged.

Capsimage32x32,kernel5x5,strict finite values+-1000. All option menus, asymmetric
hand-reference kernel, non-square image, even/odd padding, both fit axes, signed
activation, decimal unit products, caps/types/shapes and no-mutation tested.
Features have image units times supplied kernel units. No semantic feature claim.

SCOPED supplied-kernel spatial feature extraction/PARTIAL literal feature. No
kernel learning, channels/network training, pooling or semantic feature benefit,
auth/persistence/runtime integration. No external effects.
