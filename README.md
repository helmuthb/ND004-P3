# Full Stack Web Developer Nanodegree - P3: Item Catalog

This is the project 3 implementation for the Full Stack Web Developer
Nanodegree, implementing a web site based on Flask microframework,
SQLAlchemy as ORM layer, and using OAuth for authentication.

## Prerequisites

To use this program one has to have [Vagrant](http://vagrantup.com/)
and [VirtualBox](https://www.virtualbox.org/) installed.

## Running the application

Use the command line (e.g. Terminal app on OSX or Linux, or CMD on Windows).
Go to the subdirectoy directory `vagrant` and start the Vagrant VM with the
command `vagrant up`. Then connect to the VM with `vagrant ssh`:
```
  cd vagrant
  vagrant up
  vagrant ssh
```
Instead of `vagrant ssh` you can use an SSH client (e.g. putty) and connect with `localhost` on port `2222`.
Use username `vagrant` and password `vagrant` when asked for login details.

The `vm_config.sh` file has been adjusted to install the needed python libraries.
At the first run the application will create the database to store the catalog items.
```
  cd /vagrant/catalog
  python ./application.py
```

## Database layer

For simplicity reason I opted for a sqlite database. This allowed me to trigger the
initial creation of the database with a simple check for file existence.
Porting the application to e.g. PostgreSQL should not be a major issue due to the
simplicity of the data model and the use of an ORM layer.

SQLAlchemy is used as ORM layer.

## Application layer

The application is written in python using the Flask microframework.
For authentication I am using Sign-In with Google which is based on OAuth.
A small decorator helps me to signify the functions which cannot be executed
without proper authentication.

Every user with a Google account can use the application, add new elements,
and update/delete existing ones. This would have to be restricted in a real-world
example, but for simplicity I kept it like this.

## RESTful API

The API aims to follow RESTful principles. Generally the URIs are used to identify
the 'resources' (e.g. lists or objects), and the HTTP methods are used to identify
the actions performed (POST->Create, GET->Read, PUT->Update, DELETE->Delete).

The Accept-header is used to identify whether a JSON representation of the data is
requested. The request body can be urlencoded, multipart/form-data or json.

Since not all clients can manipulate the Accept-header and/or use all the HTTP
methods, two query parameters allow overriding the method and output format.
 - `operation=delete` performs a delete operation even if POST is used
 - `type=json` will create output in JSON format

## Extensions ###

The application allows the specification of an image URL for categories and catalog
items.
In addition, for deleting an object, a nonce is used to secure from replay attacks.
Every nonce is only valid for this session and for deleting the specific object.
It has to be provided with the delete operation through the `nonce` query parameter.

## Copyright and license

Some of the application codes have been copied from documentation (e.g. Google Sign-In)
or from stackoverflow (marked in the code).
My contributions are in the public domain.