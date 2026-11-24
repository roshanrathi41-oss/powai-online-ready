FROM condaforge/miniforge3:latest
WORKDIR /app
COPY environment.yml /app/environment.yml
RUN conda env create -f /app/environment.yml && conda clean -afy
ENV PATH="/opt/conda/envs/powai/bin:${PATH}"
COPY index.html /app/index.html
COPY powai-service /app/powai-service
WORKDIR /app/powai-service
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}"]
