from kivy.app import App
from kivy.uix.boxlayout import BoxLayout

from kivy_garden.webview import WebView


class ResellerApp(App):

    def build(self):

        layout = BoxLayout()

        web = WebView(
            url="https://reseller-figure-handball.ngrok-free.dev"
        )

        layout.add_widget(web)

        return layout


ResellerApp().run()