import requests
from lxml import html

class WebProcessor:

    def get_content(self, url):
        page = requests.get(url)
        return page.text
        #return html.fromstring(page.content)

    def get_body(self, url):
        page = requests.get(url)
        return html.fromstring(page.content).xpath("/html/body")[0]


    # def get_element_by_id(self, url, id):
    #     page = requests.get(url)
    #     div = html.fromstring(page.content).xpath(f'//*[@id="{id}"]')
    #     return div[0]

    def get_element_by_id(self, htmlElement, id):
        elements = htmlElement.xpath(f'//*[@id="{id}"]')
        return elements[0]


    def get_element_by_class(self, htmlElement, id):
        return self.get_elements_by_class(htmlElement, id)[0]


    def get_elements_by_class(self, htmlElement, class_name):
        return htmlElement.xpath(f'//*[@class="{class_name}"]')


    def get_element_by_data_reactid(self, htmlElement, reactId):
        elements = htmlElement.xpath(f'//*[@data-reactid="{reactId}"]')
        return elements[0]