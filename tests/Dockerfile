FROM dojot/dredd-python:3.6

RUN pip3 install cython

RUN mkdir -p /usr/src/app/requirements && mkdir /usr/src/app/auth && mkdir /usr/src/app/tests

WORKDIR /usr/src/app

COPY ./requirements/requirements.txt requirements/requirements.txt
COPY ./tests/requirements.txt tests/requirements.txt
RUN pip install -r requirements/requirements.txt -r tests/requirements.txt
COPY . /usr/src/app
RUN ["python3", "setup.py", "install"]
CMD ["./tests/start-test.sh"]
