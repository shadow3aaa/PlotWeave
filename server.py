from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "欢迎访问剧情织机 (PlotWeave) 后端"}
