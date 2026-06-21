const { Client, LocalAuth, MessageMedia } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');
const axios = require('axios');

const client = new Client({
    authStrategy: new LocalAuth(),
    puppeteer: {
        args: ['--no-sandbox', '--disable-setuid-sandbox']
    }
});

client.on('qr', (qr) => {
    console.log('\n=============================================');
    console.log('   SCAN THIS QR CODE WITH YOUR WHATSAPP');
    console.log('=============================================\n');
    qrcode.generate(qr, { small: true });
});

client.on('authenticated', () => {
    console.log('\n[✔] Authenticated successfully! Syncing chats (this may take a minute)...');
});

client.on('auth_failure', msg => {
    console.error('\n[X] Authentication failed!', msg);
});

client.on('loading_screen', (percent, message) => {
    console.log(`⏳ Loading WhatsApp Web... ${percent}%`);
});

client.on('ready', () => {
    console.log('\n✅ WhatsApp AI Voice Agent is READY!');
    console.log('Send a Voice Note to this number to test.\n');
});

client.on('message', async msg => {
    // Only process voice notes (ptt) or audio
    if (msg.hasMedia && (msg.type === 'ptt' || msg.type === 'audio')) {
        console.log(`\n📥 Received Voice Note from: ${msg.from}`);
        
        try {
            console.log('⏳ Downloading audio from WhatsApp...');
            const media = await msg.downloadMedia();
            
            console.log('🧠 Sending audio to Python AI Engine...');
            const response = await axios.post('http://localhost:8001/api/whatsapp-voice', {
                phone: msg.from,
                audio_base64: media.data
            });
            
            console.log('📤 Received AI response, sending Voice Note back...');
            
            // Convert received base64 mp3 back to WhatsApp Voice Note
            const aiAudio = new MessageMedia(
                response.data.mime_type, 
                response.data.audio_base64, 
                'reply.mp3'
            );
            
            // Send as Voice Note
            await client.sendMessage(msg.from, aiAudio, { sendAudioAsVoice: true });
            
            // Also send the text reply
            await client.sendMessage(msg.from, response.data.reply_text);
            console.log('✅ Reply sent successfully!');
            
        } catch (err) {
            console.error('❌ Error processing message:', err.message);
            msg.reply("Sorry, I am having trouble connecting to my AI brain right now.");
        }
    } else if (!msg.hasMedia && msg.body) {
        msg.reply("👋 Please send me a *Voice Note* (Audio message) to talk to the AI Admission Counselor! 🎤");
    }
});

client.initialize();
