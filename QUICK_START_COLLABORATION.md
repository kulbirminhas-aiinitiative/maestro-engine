# 🚀 Multi-Agent Collaboration - QUICK START GUIDE

## ⚡ 1-Minute Setup

### **Terminal 1: Start BFF Service**
```bash
cd /home/ec2-user/projects/maestro-v2
./start_collaboration_bff.sh
```

### **Terminal 2: Start Frontend**
```bash
cd /home/ec2-user/projects/maestro-frontend-new
npm run dev
```

### **Browser**
1. Open: `http://3.10.213.208:4200`
2. Click: **"💬 Collaboration"** tab
3. Done! 🎉

---

## 💬 Try These Commands

### **1. Start a Conversation**
```
User: "We need to build a landing page for our SaaS product"
```
**Result:** AI agents may respond based on relevance

### **2. Mention Specific Agents**
```
User: "@Stephen what requirements should we gather?"
User: "@Andy what's the best architecture?"
User: "@Sarah what should the UX look like?"
User: "@Marcus how should we structure the backend?"
User: "@Emma what frontend framework should we use?"
```
**Result:** Each agent responds with their expertise

### **3. Request Preview from Maestro**
```
User: "@Maestro create the landing page based on our discussion"
```
**Result:** Complete HTML/CSS/JS preview generated in right panel

### **4. Add Team Members**
1. Click **"+"** button in Team Panel
2. Search for AI agents (Stephen, Andy, Sarah, Marcus, Emma, Maestro)
3. Click to add them to the room

---

## 🎯 Available AI Agents

| Agent | Role | When to @mention |
|-------|------|-----------------|
| 📋 @Stephen | Requirements Analyst | Gathering requirements, user stories |
| 🏗️ @Andy | Solution Architect | System design, tech stack decisions |
| 🎨 @Sarah | UX Designer | User experience, visual design |
| ⚙️ @Marcus | Backend Developer | APIs, databases, server logic |
| 💻 @Emma | Frontend Developer | React, TypeScript, components |
| 🤖 @Maestro | Code Synthesis | **Generate complete code/preview** |

---

## ✅ Verify It's Working

### **1. Check BFF Service**
```bash
curl http://localhost:4002/health
```

**Expected:**
```json
{
  "status": "healthy",
  "service": "collaboration-bff",
  ...
}
```

### **2. Check Frontend**
- Open browser console (F12)
- Look for: `[MultiAgentChat] ✅ Connected`

### **3. Test Message Flow**
1. Type a message mentioning an agent: `@Stephen hello`
2. Should see:
   - Your message appears
   - "Stephen is typing..." indicator
   - Stephen's AI response appears

---

## 🐛 Quick Troubleshooting

### **BFF Won't Start**
```bash
# Check if port 4002 is in use
lsof -i :4002

# Kill the process if needed
kill -9 <PID>
```

### **Frontend Can't Connect**
```bash
# Verify BFF is running
curl http://localhost:4002/health

# Check frontend config points to port 4002
grep -n "4002" /home/ec2-user/projects/maestro-frontend-new/src/config/api.ts
```

### **No AI Responses**
- **Try mentioning agents explicitly:** `@Stephen @Andy`
- **Check BFF logs** for errors
- **Verify** agents are added to the room

---

## 📱 Full Example Session

```
👤 User: "Let's build a modern pricing page"

📋 Stephen: "Let me clarify the requirements. How many pricing tiers
             do you need? What's the target audience?"

👤 User: "3 tiers - basic, pro, enterprise. Target is B2B SaaS companies"

🏗️ Andy: "For B2B SaaS, I recommend a responsive grid layout with
          feature comparison tables. Should we include annual/monthly toggle?"

👤 User: "Yes, annual/monthly toggle. @Sarah what should the design look like?"

🎨 Sarah: "For B2B SaaS pricing, I recommend a clean, professional design
           with clear visual hierarchy. The enterprise tier should stand out
           as 'recommended'. Use trust signals like badges and testimonials."

👤 User: "@Emma what components do we need?"

💻 Emma: "I'll build reusable React components: PricingCard, FeatureList,
          PlanToggle. We can use TypeScript for type safety and Tailwind
          for responsive styling."

👤 User: "@Maestro create the pricing page"

🤖 Maestro: "Analyzing team discussion... Generating complete pricing page
             with 3 tiers, toggle, and professional design..."

📱 [Preview Panel shows complete, interactive pricing page]
```

---

## 🎨 Customization

### **Change AI Agent Response Frequency**

Edit `collaboration_bff_service.py`:
```python
# Line ~648: Change 0.10 to adjust spontaneous responses
if random.random() < 0.20:  # 20% chance (was 10%)
    return True
```

### **Add Your Own Agent**

See: `COLLABORATION_BFF_IMPLEMENTATION_COMPLETE.md` → "Customization Guide"

---

## 📖 Full Documentation

- **Frontend Docs:** `/home/ec2-user/projects/maestro-frontend-new/MULTI_AGENT_COLLABORATION_COMPLETE.md`
- **Backend Docs:** `/home/ec2-user/projects/maestro-v2/COLLABORATION_BFF_IMPLEMENTATION_COMPLETE.md`

---

**Need Help?** Check logs in both terminal windows for detailed error messages.

**Ready to test!** 🚀
