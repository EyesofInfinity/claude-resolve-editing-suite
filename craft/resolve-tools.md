# What DaVinci Resolve already does

Check this list before you write a script. Resolve Studio may already do the job. New Resolve versions add more, so check its scripting docs too. If nothing here fits, follow "The show must go on" in `CLAUDE.md`.

These calls are in the scripting API for Resolve 21.1. Only captions have been tested with this suite so far. Try each other call on a short piece first, and read the result back. Some need a Studio licence or an Extras download, and they return False without one.

| Job | Resolve's tool | How |
|---|---|---|
| Captions | Auto captions | `timeline.CreateSubtitlesFromAudio`. See "Captions" in `.claude/skills/make-video/SKILL.md` |
| Sync a camera to a separate recorder | Auto sync | `mediaPool.AutoSyncAudio(clips, settings)`, with `resolve.AUDIO_SYNC_WAVEFORM` for matching by sound |
| Sync several cameras | Multicam clip | `mediaPool.CreateMulticamClip(clips, options)`, with `resolve.MULTICAM_ANGLE_SYNC_AUDIO` for matching by sound |
| Vertical crops that follow the subject | Smart Reframe | `timelineItem.SmartReframe()`, then `project.GetSmartReframeStatus()` |
| Find the cuts in a finished clip | Scene cut detection | `timeline.DetectSceneCuts()`, then `project.GetDetectSceneCutsStatus()` |
| Search footage by words, faces or objects | IntelliSearch | `folder.AnalyzeForIntellisearch(identifyFaces, isBetterMode)`. The search itself is in Resolve's window |
| Remove noise behind speech | Voice Isolation | `timeline.SetVoiceIsolationState(track, state)`, or the clip's `AudioVoiceIsolationEnabled` and `AudioVoiceIsolationAmount` |
| Even out a voice | Dialogue Leveler | The clip's `AudioDialogueLevelerEnabled` and related properties |
| Match levels between clips | Normalize | `timeline.NormalizeAudioLevel(items, options)` |
| Steady a shaky shot | Stabilizer | `timelineItem.Stabilize()` |
| Build a timeline from many clips | Media pool | `mediaPool.CreateTimelineFromClips(name, [{"mediaPoolItem": c} for c in clips])`, or `AppendToTimeline` |
| Add a dissolve or other Resolve transition | Transitions | `timelineItem.AddTransition({"type": "Cross Dissolve", "category": "simple", "position": "end", "alignment": "center", "duration": frames})`. With alignment "left" and no spare frames, the shot fades to black: use "center", with half the duration spare on both sides |

Every call here changes the open project. Follow the rules in `CLAUDE.md`: read Resolve first, work on a new timeline, and leave the user's work alone.

Taste stays yours. Resolve can line up the cameras. Choosing the shots, the order and the pace is the editing, and [cutting.md](cutting.md) covers that.
