# Arkham horror 3rd Edition Companion app (server)

This is the required server to use the Arkham horror 3rd Edition Companion app. Run this somewhere in the local network and you'll be able to connect to it with the app using the server's IP address or DNS name if you set that up.

## Running the server:

Most of the ways to run the server have been turned into makefile commands to make things easier.

### Option 1: git clone, and just run it

If you have python 3.14 installed, you can git clone the project, build the virtual environment and then just run the server. 

Step 1: build the environment

``` bash
make env
companion
```

### Option 2: Run it as a docker container on the current machine

If you have docker, you can make a docker image and run that:

``` bash
make docker-build
make docker-run
```
This will build the image for the current machines architecture, then run it on port 8081.
