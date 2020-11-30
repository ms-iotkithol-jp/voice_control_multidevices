using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Microsoft.Azure.EventHubs;
using Microsoft.Azure.WebJobs;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Configuration;
using Microsoft.Azure.Devices;
using Newtonsoft.Json.Linq;

namespace EmbeddedGeorge
{
    public static class SenseHatControl
    {
        static ServiceClient serviceClient;

        [FunctionName("SenseHatControl")]
        public static async Task Run([EventHubTrigger("voicecommand", Connection = "listen_EVENTHUB")] EventData[] events, ILogger log, ExecutionContext context)
        {
            var exceptions = new List<Exception>();
            if (serviceClient == null) {
                var config = new ConfigurationBuilder().SetBasePath(context.FunctionAppDirectory).AddJsonFile("local.settings.json",optional:true, reloadOnChange: true).AddEnvironmentVariables().Build();
                var iothubcs = config.GetConnectionString("IoTHubConnectionString"); 
                serviceClient = ServiceClient.CreateFromConnectionString(iothubcs);
                await serviceClient.OpenAsync();
            }

            foreach (EventData eventData in events)
            {
                try
                {
                    string messageBody = Encoding.UTF8.GetString(eventData.Body.Array, eventData.Body.Offset, eventData.Body.Count);
                    dynamic messageJson = Newtonsoft.Json.JsonConvert.DeserializeObject(messageBody);
                    if (messageJson is JArray) {
                        foreach (dynamic mj in messageJson) {
                            await DriveTarget(mj, log);
                        }
                    }
                    else {
                        await DriveTarget(messageBody, log);
                    }
                    // Replace these two lines with your processing logic.
                    log.LogInformation($"C# Event Hub trigger function processed a message: {messageBody}");
                    await Task.Yield();
                }
                catch (Exception e)
                {
                    // We need to keep processing the rest of the batch - capture this exception and continue.
                    // Also, consider capturing details of the message that failed processing so it can be processed again later.
                    exceptions.Add(e);
                }
            }

            // Once processing of the batch is complete, if any messages in the batch failed processing throw an exception so that there is a record of the failure.

            if (exceptions.Count > 1)
                throw new AggregateException(exceptions);

            if (exceptions.Count == 1)
                throw exceptions.Single();
        }

        public static async Task DriveTarget(dynamic messageJson, ILogger log)
        {
            string deviceid = messageJson["deviceid"];
            string word = messageJson["word"];
            string destination = messageJson["destination"];
            log.LogInformation($"Received - deviceid={deviceid},word={word},destination={destination}");
            string modulename = "sensehatdisplay";
            var methodName = "";
            var payload = "";
            if (word == "japan") {
                methodName = "ShowText";
                payload = "{\"text\":\"Japan\",\"forground\":[255,0,0],\"background\":[0,0,0],\"float\":0.5}";
            }
            else if (word == "led") {
                methodName = "ShowImage";
                payload = "{\"image\":\"[[0,0,0],[0,0,0],[20,0,0],[255,0,0],[20,0,0],[0,0,0],[0,0,0],[0,0,0]],[[0,0,0],[0,0,0],[24,0,0],[255,0,0],[255,0,0],[35,0,0],[255,0,0],[0,0,0]],[[0,0,0],[21,0,0],[255,0,0],[255,0,0],[250,192,0],[255,0,0],[255,0,0],[0,0,0]],[[0,0,0],[255,0,0],[255,0,0],[250,192,0],[250,192,0],[250,100,0],[255,0,0],[255,0,0]],[[255,0,0],[255,0,0],[255,102,0],[250,192,0],[255,255,0],[250,190,0],[255,0,0],[255,0,0]],[[0,0,0],[255,0,0],[255,0,0],[250,192,0],[255,255,0],[250,190,0],[255,0,0],[0,0,0]],[[0,0,0],[41,0,0],[255,0,0],[250,102,0],[255,192,0],[250,0,0],[0,0,0],[0,0,0]],[[0,0,0],[0,0,0],[31,0,0],[255,0,0],[255,0,0],[255,100,0],[0,0,0],[0,0,0]]\"}";
            }
            else if (word == "clear") {
                methodName = "Clear";
                payload = "{\"color\":[0,0,0]}";
            }
            if (!string.IsNullOrEmpty(methodName)) {
                var c2dMethod = new CloudToDeviceMethod(methodName);
                if (!string.IsNullOrEmpty(payload)) {
                    c2dMethod.SetPayloadJson(payload);
                }
                log.LogInformation($"Invoking method - {methodName}({payload})");
                try{
                    var response = await serviceClient.InvokeDeviceMethodAsync(destination, modulename, c2dMethod);
                    log.LogInformation($"Invoked response - {response.Status}:{response.GetPayloadAsJson()}");
                }
                catch (Exception ex) {
                    log.LogInformation($"Exception - {ex.Message}");
                }
            }
        }
    }
}
