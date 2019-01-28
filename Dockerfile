FROM python:3.6-alpine as basis

RUN apk update && apk --no-cache add build-base postgresql-dev libffi-dev git libc6-compat linux-headers bash dumb-init

RUN pip install cython

RUN mkdir -p /usr/src/app/requirements
WORKDIR /usr/src/app

RUN python3 -m venv /usr/src/venv
ENV VIRTUAL_ENV="/usr/src/venv"
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

COPY requirements/requirements.txt requirements/requirements.txt
RUN pip install -r requirements/requirements.txt
ADD . /usr/src/app

FROM python:3.6-alpine

COPY --from=basis /usr/src/venv /usr/src/venv
COPY --from=basis /usr/src/app /usr/src/app

RUN apk update && apk --no-cache add libpq libstdc++ curl

ENV VIRTUAL_ENV="/usr/src/venv"
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
ENV PYTHONPATH="/usr/src/app"
WORKDIR /usr/src/app

EXPOSE 5000

HEALTHCHECK --interval=10s --timeout=30s --start-period=20s --retries=5 CMD curl -f http://localhost:5000/healthcheck || exit 1

CMD ["sh", "./appRun.sh", "start"]
