const express = require('express')
const app = express()

app.get('/', (req, res) =>
{
    res.send(`
        <html>
        <head>
            <title>MERN Dev Environment</title>
        </head>
        <body style="font-family: Arial; text-align:center; padding:50px;">
            <h1>🚀 MERN Dev Environment</h1>
            <h2>Running Successfully ✅</h2>
            <p>This is your live container environment</p>

            <button onclick="alert('Backend Connected!')">
                Test Backend
            </button>
        </body>
        </html>
    `)
})

app.listen(80, '0.0.0.0', () =>
{
    console.log("Server running on port 80")
})
