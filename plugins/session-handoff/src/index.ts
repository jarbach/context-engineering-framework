/**
 * Session Handoff Generator Plugin
 * 
 * Automatically generates handoff artifacts when sessions close,
 * capturing framing changes, boundaries, corrections, and unresolved tensions.
 */

import { definePluginEntry } from "openclaw/plugin-sdk/plugin-entry";

export default definePluginEntry({
  id: "session-handoff",
  name: "Session Handoff Generator",
  
  register(api) {
    // Listen for session end events
    api.on("session_end", async (event) => {
      const { sessionKey, sessionId, reason } = event;
      
      // Skip trivial sessions (less than 5 turns)
      if (event.context.messageCount < 5) {
        console.log(`[session-handoff] Skipping session ${sessionId} (${event.context.messageCount} turns)`);
        return;
      }
      
      console.log(`[session-handoff] Session ended: ${sessionId} (reason: ${reason})`);
      
      try {
        // Get transcript path from session metadata
        const transcriptPath = event.context.transcriptPath;
        
        if (!transcriptPath) {
          console.error(`[session-handoff] No transcript path for session ${sessionId}`);
          return;
        }
        
        // Generate handoff artifact
        const outputDir = `${process.env.OPENCLAW_WORKSPACE_DIR || '.'}/memory/handoffs`;
        const outputPath = `${outputDir}/${sessionId}-handoff.md`;
        
        console.log(`[session-handoff] Generating handoff: ${outputPath}`);
        
        // Execute handoff generator
        const { execFile } = await import('node:child_process');
        const { promisify } = await import('node:util');
        const execFileAsync = promisify(execFile);
        
        await execFileAsync('./skills/session-handoff-generator/generate-handoff.py', [
          '--transcript-file', transcriptPath,
          '--output', outputPath
        ], {
          cwd: process.env.OPENCLAW_WORKSPACE_DIR || '.',
          timeout: 30000 // 30 second timeout
        });
        
        console.log(`[session-handoff] ✓ Handoff generated: ${outputPath}`);
        
        // Notify user (only for certain session end reasons)
        if (reason === 'idle' || reason === 'deleted') {
          event.messages.push(`📝 Session handoff draft created: \`memory/handoffs/${sessionId}-handoff.md\``);
          event.messages.push('Review with: `./skills/session-handoff-generator/review-handoff.sh <file>`');
        }
        
      } catch (error) {
        console.error(`[session-handoff] Error generating handoff:`, error);
        event.messages.push(`⚠️ Handoff generation failed for session ${sessionId}`);
      }
    }, { priority: 50 });
  },
});
