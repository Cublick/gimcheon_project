# __init__.py 폴더에서 가장 먼저 실행

# import sys, os
# sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__)))) # 상위폴더 접근

from . import review, rank, rank_menu, autocomplete, graph, weather, graph_top
from flask import jsonify,  Flask, request, redirect
from flasgger import Swagger

app = Flask(__name__)

app.register_blueprint(review.review) # blueprint : flask에서 제공하는 라이브러리, (파일명.menutest파일에서의 me_ca 사용할 명)
app.register_blueprint(rank.rank)
app.register_blueprint(rank_menu.rank_menu)
app.register_blueprint(autocomplete.autocomplete)
app.register_blueprint(graph.graph)
app.register_blueprint(weather.weather)
app.register_blueprint(graph_top.graph_top)


@app.route("/")
def hello():

    return "Cublick Digital"