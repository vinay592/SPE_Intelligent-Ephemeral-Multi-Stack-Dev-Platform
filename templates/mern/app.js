const express = require('express')
const app = express()

app.use(express.json())

let codeStore = "console.log('Hello MERN 🚀')"

app.get('/', (req, res) => {
    res.send(`
        <h2>MERN Dev Environment 🚀</h2>
        <form method="POST" action="/run">
            <textarea name="code" rows="10" cols="50">${codeStore}</textarea><br><br>
            <button type="submit">Run</button>
        </form>
    `)
})

app.post('/run', express.urlencoded({ extended: true }), (req, res) => {
    codeStore = req.body.code

    let output = ""
    try {
        eval(codeStore)
        output = "Executed ,successfully"
    } catch (e) {
        output = e.toString()
    }

    res.send(`
        <h2>MERN Dev Environment 🚀</h2>
        <form method="POST" action="/run">
            <textarea name="code" rows="10" cols="50">${codeStore}</textarea><br><br>
            <button type="submit">Run</button>
        </form>
        <h3>${output}</h3>
    `)
})

app.listen(3000, '0.0.0.0', () => {
    console.log("Server running on port 3000")
})
