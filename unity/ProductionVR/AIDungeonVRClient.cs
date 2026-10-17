// unity/ProductionVR/AIDungeonVRClient.cs
// Production-grade Unity XR client for AI Dungeon Master.
// Handles asynchronous lifecycle, physical dice roll dispatch, and world-space GenUI rendering.

using System;
using System.Collections;
using System.Collections.Generic;
using System.Text;
using UnityEngine;
using UnityEngine.Networking;

namespace AIDungeonMaster.VR
{
    [DisallowMultipleComponent]
    public class AIDungeonVRClient : MonoBehaviour
    {
        [Header("Backend Configuration")]
        [Tooltip("Local or remote AI Dungeon Master server host")]
        [SerializeField] private string serverBaseUrl = "http://localhost:8000";

        [Header("VR Spatial Settings")]
        [Tooltip("World-space canvas for displaying active GenUI surface")]
        [SerializeField] private Canvas worldSpaceCanvas;
        [Tooltip("Physical virtual dice tray detector")]
        [SerializeField] private Transform physicalDiceTray;

        // Structured JSON Envelope Models matching agentsurface-blueprint/0.1
        [Serializable]
        public class SurfacePayload
        {
            public string contract;
            public BlueprintWrapper blueprint;
            public HeroStats hero;
            public string surfaceType;
        }

        [Serializable]
        public class BlueprintWrapper
        {
            public SurfaceHeader surface;
            public string[] intents;
        }

        [Serializable]
        public class SurfaceHeader
        {
            public string id;
            public string title;
            public string subtitle;
            public string width;
        }

        [Serializable]
        public class HeroStats
        {
            public string name;
            public string archetype;
            public int level;
            public int hp;
            public int maxHp;
            public int ac;
            public string edition;
            public bool confirmed;
        }

        [Serializable]
        public class IntentRequest
        {
            public string intent;
            public Dictionary<string, object> values;
        }

        [Serializable]
        public class IntentResponse
        {
            public BlueprintWrapper blueprint;
            public HeroStats hero;
        }

        // Public lifecycle events for VR systems (Audio, Haptics, Avatar Anim)
        public event Action<BlueprintWrapper, HeroStats> OnSurfaceUpdated;
        public event Action<string> OnNarrativeVoiceCue;
        public event Action<string> OnErrorReceived;

        public HeroStats CurrentHero { get; private set; }
        public BlueprintWrapper CurrentBlueprint { get; private set; }

        private void Start()
        {
            StartCoroutine(FetchActiveSurface());
        }

        /// <summary>
        /// Pull current active surface and character sheet on scene load.
        /// </summary>
        public IEnumerator FetchActiveSurface()
        {
            string url = $"{serverBaseUrl}/api/surface";
            using UnityWebRequest req = UnityWebRequest.Get(url);
            req.timeout = 5;
            yield return req.SendWebRequest();

            if (req.result != UnityWebRequest.Result.Success)
            {
                string err = $"[VR Client] Failed to reach DM server: {req.error}";
                Debug.LogError(err);
                OnErrorReceived?.Invoke(err);
                yield break;
            }

            try
            {
                var payload = JsonUtility.FromJson<SurfacePayload>(req.downloadHandler.text);
                CurrentBlueprint = payload.blueprint;
                CurrentHero = payload.hero;
                OnSurfaceUpdated?.Invoke(CurrentBlueprint, CurrentHero);
                Debug.Log($"[VR Client] Active surface loaded: {CurrentBlueprint.surface.title} for {CurrentHero.name}");
            }
            catch (Exception ex)
            {
                Debug.LogError($"[VR Client] Serialization error: {ex.Message}");
            }
        }

        /// <summary>
        /// Dispatch an intent triggered by VR laser pointer, button press, or hand gesture.
        /// </summary>
        public void DispatchVRIntent(string intentName, Dictionary<string, object> values = null)
        {
            StartCoroutine(PostIntentRoutine(intentName, values ?? new Dictionary<string, object>()));
        }

        /// <summary>
        /// Called when the player physically picks up and rolls a 3D d20 die in VR space.
        /// </summary>
        public void ReportPhysicalDiceRoll(int diceValue)
        {
            var values = new Dictionary<string, object> { { "roll", diceValue } };
            DispatchVRIntent("PHYSICAL_DICE_ROLL", values);
        }

        private IEnumerator PostIntentRoutine(string intentName, Dictionary<string, object> values)
        {
            string url = $"{serverBaseUrl}/api/intent";
            
            // Build simple JSON payload
            string jsonBody = "{\"intent\":\"" + intentName + "\"}";

            using UnityWebRequest req = new UnityWebRequest(url, "POST")
            {
                uploadHandler = new UploadHandlerRaw(Encoding.UTF8.GetBytes(jsonBody)),
                downloadHandler = new DownloadHandlerBuffer()
            };
            req.SetRequestHeader("Content-Type", "application/json");
            req.timeout = 5;

            yield return req.SendWebRequest();

            if (req.result != UnityWebRequest.Result.Success)
            {
                string err = $"[VR Client] Intent dispatch failed: {req.error}";
                Debug.LogWarning(err);
                OnErrorReceived?.Invoke(err);
                yield break;
            }

            try
            {
                var resp = JsonUtility.FromJson<IntentResponse>(req.downloadHandler.text);
                CurrentBlueprint = resp.blueprint;
                CurrentHero = resp.hero;
                OnSurfaceUpdated?.Invoke(CurrentBlueprint, CurrentHero);
                Debug.Log($"[VR Client] State updated after {intentName}.");
            }
            catch (Exception ex)
            {
                Debug.LogError($"[VR Client] Failed to parse intent response: {ex.Message}");
            }
        }
    }
}
