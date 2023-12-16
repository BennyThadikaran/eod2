# FROM pandas/pandas:alpine
FROM python:3.8.18-slim-bullseye

WORKDIR /app

RUN apt update && apt upgrade && apt install -y python3-tk
RUN pip install -U pandas requests nse

RUN mkdir -p defs/ eod2_data/daily/

COPY init.py .

COPY eod2_data/isin.csv eod2_data/meta.json eod2_data/sector_watchlist.csv ./eod2_data/

COPY defs/defs.py defs/Dates.py defs/Config.py defs/utils.py ./defs/

CMD ["python3", "init.py"]
