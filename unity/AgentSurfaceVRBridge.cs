// unity/AgentSurfaceVRBridge.cs - Minimal zero-dependency Unity VR bridge for agentsurface-blueprint/0.1
using System;
using System.Collections;
using System.Text;
using UnityEngine;
using UnityEngine.Networking;

public class AgentSurfaceVRBridge : MonoBehaviour
{
    [SerializeField] private string serverUrl = "http://localhost:8000/demo-data.json";
    [SerializeField] private string intentUrl = "http://localhost:8000/api/intent";

    [Serializable] public class SurfaceMeta { public string id; public string title; public string subtitle; }
    [Serializable] public class BlueprintEnvelope { public SurfaceMeta surface; }
    [Serializable] public class IntentPayload { public string surface; public string intent; public string ts; }

    public IEnumerator FetchActiveSurface(Action<string> onLoaded)
    {
        using UnityWebRequest req = UnityWebRequest.Get(serverUrl);
        yield return req.SendWebRequest();
        if (req.result == UnityWebRequest.Result.Success) onLoaded?.Invoke(req.downloadHandler.text);
        else Debug.LogError($"[VR Bridge] Fetch failed: {req.error}");
    }

    public IEnumerator DispatchVRIntent(string surfaceId, string intentName)
    {
        var payload = new IntentPayload { surface = surfaceId, intent = intentName, ts = DateTime.UtcNow.ToString("o") };
        string json = JsonUtility.ToJson(payload);
        using UnityWebRequest req = new UnityWebRequest(intentUrl, "POST")
        {
            uploadHandler = new UploadHandlerRaw(Encoding.UTF8.GetBytes(json)),
            downloadHandler = new DownloadHandlerBuffer()
        };
        req.SetRequestHeader("Content-Type", "application/json");
        yield return req.SendWebRequest();
        Debug.Log($"[VR Bridge] Intent {intentName} dispatched: {req.responseCode}");
    }
}
