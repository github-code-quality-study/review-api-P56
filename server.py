import nltk
from nltk.sentiment.vader import SentimentIntensityAnalyzer
from nltk.corpus import stopwords
from urllib.parse import parse_qs, urlparse, unquote
import json
import pandas as pd
from datetime import datetime
import uuid
import os
from typing import Callable, Any
from wsgiref.simple_server import make_server

nltk.download('vader_lexicon', quiet=True)
nltk.download('punkt', quiet=True)
nltk.download('averaged_perceptron_tagger', quiet=True)
nltk.download('stopwords', quiet=True)

adj_noun_pairs_count = {}
sia = SentimentIntensityAnalyzer()
stop_words = set(stopwords.words('english'))

reviews = pd.read_csv('data/reviews.csv').to_dict('records')

class ReviewAnalyzerServer:
    def __init__(self) -> None:
        # This method is a placeholder for future initialization logic
        pass

    def analyze_sentiment(self, review_body):
        sentiment_scores = sia.polarity_scores(review_body)
        return sentiment_scores
    
    def start_date_extractor(self, data):
        print("start date found")
        new_response = []
        start_date = data.split('start_date=')[1]

        if '&' in start_date:
            start_date = start_date.split("&")[0]
        else:
            start_date = start_date.split("'")[0]
        print('start_date - ',start_date)

        for response in reviews:
            
            if int(response['Timestamp'].split(' ')[0].replace('-','')) >= int(start_date.replace('-','')):
                new_response.append(response)
        return new_response  
    
    def end_date_extractor(self, data):
        print("end date found")
        new_response = []

        end_date = data.split('end_date=')[1]
        if '&' in end_date:
            end_date = end_date.split("&")[0]
        else:
            end_date = end_date.split("',")[0]

        for response in reviews:
            if int(response['Timestamp'].split(' ')[0].replace('-','')) <= int(end_date.replace('-','')):
                new_response.append(response)
        return new_response

    def both_date_extractor(self,data):
        print("both date found")
        new_response = []
        start_date = data.split('start_date=')[1].split("&")[0]
        end_date = data.split('end_date=')[1].split("',")[0]
        print(f'start date - {start_date}')
        print(f'end date - {end_date}')
        for response in reviews:
                if int(response['Timestamp'].split(' ')[0].replace('-','')) >= int(start_date.replace('-','')) and int(response['Timestamp'].split(' ')[0].replace('-','')) <= int(end_date.replace('-','')) :
                    # print(f'database start date - {int(response['Timestamp'].split(' ')[0].replace('-',''))}')
                    # print(f'user start date {int(start_date.replace('-',''))}')
                    new_response.append(response)
        if not new_response:
            new_response.append('NO_DATA_FOUND')
        return new_response
    
    def location_extractor(self,data):
        print("location parameter found, function called..")
        new_response = []
        input_location = data.split("location=")[1].split("'")[0]

        input_location = unquote(input_location)
        print(f'Input location = {input_location}')

        if '+' in input_location: input_location=input_location.replace('+','')
        input_location = input_location.replace(' ','')

        for review in reviews:
            if review['Location'].replace(' ','') == input_location:
                new_response.append(review)
        return new_response
    
    def sort_by_compound(self,input_reviews):
        
        sorted_reviews = []
        for review in input_reviews:
            input_reviews[input_reviews.index(review)]['sentiment'] = self.analyze_sentiment(review['ReviewBody'])
            
        sorted_reviews =  sorted(input_reviews, key=lambda current_sentiment:current_sentiment['sentiment']['compound'])
        
        return sorted_reviews
    
    def get_current_datetime(self):
        current_time = datetime.now()
        date = current_time.strftime("%Y-%m-%d")
        time = current_time.strftime(f'{current_time.hour}:%M:%S')
        correct_format = f'{date} {time}'
        return correct_format
    
    def add_review(self,review_body):
        unique_id = uuid.uuid4()
        location = review_body['Location'][0]
        review_text = review_body['ReviewBody'][0]
        correct_time_format = self.get_current_datetime()
        data_to_write = f'{str(unique_id)},"{location}",{correct_time_format},"{review_text}"'
        
        response_data = {"ReviewId":str(unique_id),
                "Location":location,
                "Timestamp":correct_time_format,
                "ReviewBody":review_text,
                "sentiment":self.analyze_sentiment(review_text)}
        return [data_to_write,response_data]



    def __call__(self, environ: dict[str, Any], start_response: Callable[..., Any]) -> bytes:
        """
        The environ parameter is a dictionary containing some useful
        HTTP request information such as: REQUEST_METHOD, CONTENT_LENGTH, QUERY_STRING,
        PATH_INFO, CONTENT_TYPE, etc.
        """

        if environ["REQUEST_METHOD"] == "GET":
            # Create the response body from the reviews and convert to a JSON byte string
            response_body = json.dumps(reviews, indent=2).encode("utf-8")
            
            # Write your code here
            data = str(environ)

            new_response = []

            if 'start_date' in data and 'end_date' in data:
                new_response = self.both_date_extractor(data)
            
            elif 'start_date' in data:
                new_response = self.start_date_extractor(data)
            elif 'end_date' in data:
                new_response = self.end_date_extractor(data)
            
            elif 'location' in data:
                new_response = self.location_extractor(data)
                print('nothing happens')
            
            
            print("Analyse sentiment response -"  ,self.analyze_sentiment(reviews[0]['ReviewBody']))
            if 'NO_DATA_FOUND' in new_response:
                new_response = [] #set the value to none because no data is found 
                response_body = json.dumps(new_response, indent=2).encode("utf-8")
            elif new_response:
                new_response = self.sort_by_compound(new_response)
                response_body = json.dumps(new_response, indent=2).encode("utf-8")
            else:
                sorted_reviews = self.sort_by_compound(reviews)
                response_body = json.dumps(sorted_reviews, indent=2).encode("utf-8")

            # Set the appropriate response headers
            start_response("200 OK", [
            ("Content-Type", "application/json"),
            ("Content-Length", str(len(response_body)))
             ])
            

            
            return [response_body]


        if environ["REQUEST_METHOD"] == "POST":
            # Write your code here
            content_length = int(environ.get('CONTENT_LENGTH',0))
            request_body = environ['wsgi.input'].readline(content_length).decode('utf-8')
            params = parse_qs(request_body)
            print(f'The parameters are {params}')
            if 'Location' in params and 'ReviewBody' in params and params['Location'][0] != 'Cupertino, California':
                output = self.add_review(params)
            else:
                response_body = 'location or review missing'
                start_response("400 INVALID_REQUEST", [
                ("Content-Type", "application/json"),
                ("Content-Length", str(len(response_body)))
                ])
                return [response_body.encode('utf-8')]


            

            response_body = json.dumps(output[1], indent=2).encode("utf-8")

            start_response("201 OK", [
            ("Content-Type", "application/json"),
            ("Content-Length", str(len(response_body)))
             ])
            
            with open('data/reviews.csv','a')as database:
                database.write(f'\n{output[0]}')
            
            return [response_body]

if __name__ == "__main__":
    app = ReviewAnalyzerServer()
    port = os.environ.get('PORT', 8000)
    with make_server("", port, app) as httpd:
        print(f"Listening on port {port}...")
        httpd.serve_forever()