from routes import app
from flasgger import Swagger
from flask_cors import CORS

app.config['SWAGGER'] = {
    'title': 'BigData API', # apidocs의 타이틀 부분
    'uiversion': 3, # swagger ui 버전
    'description': "This is cublick digital server.\n\n 각 메뉴를 클릭 후, Try it out 클릭 후 Execute 클릭하여 실행"
                   "\n keyword가 필요한 경우 : Try it out 클릭 후 keyword 입력 후 Execute 클릭하여 실행", # 설명글
    'termsOfService': None, # 부가설명 제거

}
CORS(app)
#CORS 서버는 Access-Control-Allow-Origin: *  으로 응답 모든 도메인에서 접근할 수 있음을 의미
cors = CORS(app, resources={r"/api/*": {"origins": "*"}})

#/apidocs 에서 확인 참고페이지 https://github.com/flasgger/flasgger
swagger = Swagger(app)
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=3000, threaded=True, debug=True) # 포트3천번으로 실행
