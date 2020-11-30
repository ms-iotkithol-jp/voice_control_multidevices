using Microsoft.Azure.Devices.Client;
using Microsoft.Azure.Devices.Shared;
using Newtonsoft.Json.Linq;
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Runtime.InteropServices.WindowsRuntime;
using System.Text;
using System.Threading.Tasks;
using Windows.Foundation;
using Windows.Foundation.Collections;
using Windows.Media.SpeechRecognition;
using Windows.UI.Xaml;
using Windows.UI.Xaml.Controls;
using Windows.UI.Xaml.Controls.Primitives;
using Windows.UI.Xaml.Data;
using Windows.UI.Xaml.Input;
using Windows.UI.Xaml.Media;
using Windows.UI.Xaml.Navigation;

// 空白ページの項目テンプレートについては、https://go.microsoft.com/fwlink/?LinkId=402352&clcid=0x411 を参照してください

namespace UWPAppVoice
{
    /// <summary>
    /// それ自体で使用できる空白ページまたはフレーム内に移動できる空白ページ。
    /// </summary>
    public sealed partial class MainPage : Page
    {
        private static string iothubCS = "<- Azure IoT Hub Connection String of IoT Device ->";
        DeviceClient deviceClient;
        public MainPage()
        {
            this.InitializeComponent();
            this.Loaded += MainPage_Loaded;
        }

        private async Task ShowLog(string content)
        {
            await this.Dispatcher.RunAsync(Windows.UI.Core.CoreDispatcherPriority.Normal, () =>
            {
                var sb = new StringBuilder();
                using (var writer = new StringWriter(sb))
                {
                    writer.WriteLine(content);
                    writer.Write(tbLog.Text);
                    tbLog.Text = sb.ToString();
                }
            });
        }

        private async void MainPage_Loaded(object sender, RoutedEventArgs e)
        {
            deviceClient = DeviceClient.CreateFromConnectionString(iothubCS);
            try
            {
                deviceClient.SetConnectionStatusChangesHandler(IoTHubStatusChanged);
                await deviceClient.SetDesiredPropertyUpdateCallbackAsync(IoTHubDesiredPropertyUpdated, this);
                await deviceClient.SetMethodDefaultHandlerAsync(IoTHubMethodInvoked, this);
                await deviceClient.SetReceiveMessageHandlerAsync(IoTHubMessageReceived, this);
                await deviceClient.OpenAsync();
                ShowLog("IoT Hub Connected.");
                var twin = await deviceClient.GetTwinAsync();
                ResolveDesreidProperties(twin.Properties.Desired.ToJson());
            }
            catch(Exception ex)
            {
                ShowLog(ex.Message);
            }
        }

        private async Task IoTHubMessageReceived(Message message, object userContext)
        {
            ShowLog($"Received message - '{System.Text.Encoding.UTF8.GetString(message.GetBytes())}'");
            foreach(var key in message.Properties.Keys)
            {
                ShowLog($"  {key}:{message.Properties[key]}");
            }
        }

        private async Task<MethodResponse> IoTHubMethodInvoked(MethodRequest methodRequest, object userContext)
        {
            ShowLog($"Receive Direct Method Invocation - '{methodRequest.Name}'({methodRequest.DataAsJson})");
            var response = new MethodResponse(200);
            return response;
        }

        private async Task IoTHubDesiredPropertyUpdated(TwinCollection desiredProperties, object userContext)
        {
            var dp = desiredProperties.ToJson();
            ResolveDesreidProperties(dp);
        }

        private void ResolveDesreidProperties(string dp)
        {
            var dpJson = Newtonsoft.Json.JsonConvert.DeserializeObject(dp) as JObject;
            if (dpJson.ContainsKey("voice_command"))
            {
                var voiceCommand = dpJson["voice_command"];
                voiceKeywords = voiceCommand["keywords"].Value<string>();
            }
        }

        string voiceKeywords = "光れ,led,ライト,japan,ジャパン,クリア,clear";

        private void IoTHubStatusChanged(ConnectionStatus status, ConnectionStatusChangeReason reason)
        {
            ShowLog($"IoT Hub Status Changed - State={status.ToString()},Reason={reason.ToString()}");
        }

        private async void buttonVoice_Click(object sender, RoutedEventArgs e)
        {
            // 音声認識をやるには。。。
            // Windowsの設定で'オンライン音声認識'を検索しオンにする
            var language = new Windows.Globalization.Language("ja-JP");
            var slangs = SpeechRecognizer.SupportedTopicLanguages;
            foreach (var slang in slangs)
            {
                var name = slang.DisplayName;
            }
            var langs = SpeechRecognizer.SupportedGrammarLanguages;
            foreach (var lang in langs)
            {
                var name = lang.DisplayName;
            }
            // Create an instance of SpeechRecognizer.
            var speechRecognizer = new SpeechRecognizer(language);
            

            // Listen for audio input issues.
            speechRecognizer.RecognitionQualityDegrading += SpeechRecognizer_RecognitionQualityDegrading;

            // Add a web search grammar to the recognizer.
            var webSearchGrammar = new SpeechRecognitionTopicConstraint(SpeechRecognitionScenario.WebSearch, "webSearch");

            speechRecognizer.UIOptions.AudiblePrompt = "Say magic word...";
            speechRecognizer.UIOptions.ExampleText = voiceKeywords;
            await speechRecognizer.CompileConstraintsAsync();

            // Start recognition.
            var speechRecognitionResult = await speechRecognizer.RecognizeWithUIAsync();
            //await speechRecognizer.RecognizeWithUIAsync();

            ShowLog($"Speech Recoginition Result - '{speechRecognitionResult.Text}'");
            var resultWord = speechRecognitionResult.Text;
            var voiceKeys = voiceKeywords.Split(",");
            
            if (voiceKeys.Where(i => i.ToLower().Contains(resultWord.ToLower())).Count()>0)
            {
                if (resultWord=="ジャパン")
                {
                    resultWord = "japan";
                }
                if (resultWord == "クリア")
                {
                    resultWord = "clear";
                }
                if (!string.IsNullOrEmpty(resultWord))
                {
                    var orderToTarget = new
                    {
                        word = resultWord,
                        timestamp = DateTime.Now
                    };
                    var content = Newtonsoft.Json.JsonConvert.SerializeObject(orderToTarget);
                    var msg = new Message(System.Text.Encoding.UTF8.GetBytes(content));
                    msg.Properties.Add("app", "led");
                    await deviceClient.SendEventAsync(msg);
                    ShowLog($"Send to IoT Hub - '{content}'");
                }
            }
        }

        private void SpeechRecognizer_RecognitionQualityDegrading(SpeechRecognizer sender, SpeechRecognitionQualityDegradingEventArgs args)
        {
            ShowLog($"SpeechRecognizer QualityDegrading - {args.Problem.ToString()}");
        }
    }
}
