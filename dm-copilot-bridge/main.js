/**
 * 🐉 DM Co-Pilot | Native Foundry VTT Bridge
 * Version 1.0.0
 * This script initializes the module, registers the API listener,
 * and handles the incoming JSON payloads from the cloud webhooks.
 */

Hooks.once('init', async function() {
    console.log('🐉 DM Co-Pilot | Initializing Native VTT Bridge...');
});

Hooks.once('ready', async function() {
    // SECURITY: Only the Dungeon Master can receive and process payloads
    if (!game.user.isGM) return; 

    console.log('🐉 DM Co-Pilot | Bridge Ready. Awaiting transmissions from the weave...');
    
    // Register a custom socket/listener for the DM Co-Pilot cloud app
    game.socket.on('module.dm-copilot-bridge', async (data) => {
        console.log('🐉 DM Co-Pilot | Payload Received!', data);
        
        if (data.entityType === 'Actor') {
            await handleActorImport(data.payload);
        } else if (data.entityType === 'JournalEntry') {
            await handleJournalImport(data.payload);
        }
    });
});

/**
 * Handles the creation of Monster/NPC tokens.
 */
async function handleActorImport(actorData) {
    try {
        const actor = await Actor.create(actorData);
        ui.notifications.info(`🐉 DM Co-Pilot | Successfully materialized: ${actor.name}`);
    } catch (error) {
        console.error('🐉 DM Co-Pilot | Failed to forge actor:', error);
        ui.notifications.error(`DM Co-Pilot Error: Could not materialize actor. See console.`);
    }
}

/**
 * Handles the creation of Session Recaps, Handouts, and Lore.
 */
async function handleJournalImport(journalData) {
    try {
        const journal = await JournalEntry.create(journalData);
        ui.notifications.info(`🐉 DM Co-Pilot | Successfully scribed: ${journal.name}`);
    } catch (error) {
        console.error('🐉 DM Co-Pilot | Failed to scribe journal:', error);
        ui.notifications.error(`DM Co-Pilot Error: Could not scribe journal. See console.`);
    }
}
